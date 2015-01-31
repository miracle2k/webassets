"""Different :class:`Bundle`-related tests. The big, general chunks are in
``test_bundle_build`` and ``test_bundle_urls``, this contains tests for more
specific features/aspects, like "globbing" or "versions".
"""

from __future__ import with_statement

import copy
from os import path
try:
    from urllib.request import \
        HTTPHandler, build_opener, install_opener, addinfourl
except ImportError: # Py2
    from urllib2 import HTTPHandler, build_opener, install_opener, addinfourl
from webassets.six import StringIO
from webassets.six.moves import filter

from nose.tools import assert_raises, assert_equal
from nose import SkipTest

from webassets import Bundle
from webassets.utils import set
from webassets.bundle import get_all_bundle_files
from webassets.env import Environment
from webassets.exceptions import BundleError, BuildError
from webassets.filter import Filter
from webassets.updater import TimestampUpdater, SKIP_CACHE
from webassets.version import Manifest, Version, VersionIndeterminableError

from .helpers import (
    TempEnvironmentHelper, assert_raises_regex)


class TestBundleConfig(TempEnvironmentHelper):

    def test_unknown_init_kwargs(self):
        """We used to silently ignore unsupported kwargs, which can make
        mistakes harder to track down; in particular "filters" vs "filter"
        is confusing. Now we raise an error.
        """
        try:
            Bundle(yaddayada=True)
        except TypeError as e:
            assert "unexpected keyword argument" in ("%s" % e)
        else:
            raise Exception('Expected TypeError not raised')

    def test_init_extra_kwarg(self):
        """Bundles may be given an ``extra`` dictionary."""
        assert Bundle().extra == {}
        assert Bundle(extra={'foo': 'bar'}).extra == {'foo': 'bar'}

        # Nested extra values
        assert Bundle(Bundle(extra={'foo': 'bar'}),
                      Bundle(extra={'baz': 'qux'})).extra == {
            'foo': 'bar', 'baz': 'qux'}

        # [Regression] None values in child bundles raise no exception
        bundle = Bundle('foo')
        bundle.extra = None
        assert Bundle(bundle).extra == {}

    def test_post_init_set_debug_to_True(self):
        bundle = Bundle()
        bundle.debug = True
        assert bundle.debug is True

    def test_post_init_set_debug_to_False(self):
        bundle = Bundle()
        bundle.debug = False
        assert bundle.debug is False

    def test_filter_assign(self):
        """Test the different ways we can assign filters to the bundle.
        """
        class TestFilter(Filter):
            pass

        def _assert(list, length):
            """Confirm that everything in the list is a filter instance,
            and that the list as the required length."""
            assert len(list) == length
            assert bool([f for f in list if isinstance(f, Filter)])

        # Comma-separated string.
        b = self.mkbundle(filters='jsmin,cssutils')
        _assert(b.filters, 2)
        # Whitespace is ignored.
        b = self.mkbundle(filters=' jsmin, cssutils ')
        _assert(b.filters, 2)

        # List of strings.
        b = self.mkbundle(filters=['jsmin', 'cssutils'])
        _assert(b.filters, 2)
        # Strings inside a list may not be further comma separated
        assert_raises(ValueError, self.mkbundle, filters=['jsmin,cssutils'])

        # A single or multiple classes may be given
        b = self.mkbundle(filters=TestFilter)
        _assert(b.filters, 1)
        b = self.mkbundle(filters=[TestFilter, TestFilter, TestFilter])
        _assert(b.filters, 3)

        # A single or multiple instance may be given
        b = self.mkbundle(filters=TestFilter())
        _assert(b.filters, 1)
        b = self.mkbundle(filters=[TestFilter(), TestFilter(), TestFilter()])
        _assert(b.filters, 3)

        # You can mix instances and classes
        b = self.mkbundle(filters=[TestFilter, TestFilter()])
        _assert(b.filters, 2)

        # If something is wrong, an error is raised right away.
        assert_raises(ValueError, self.mkbundle, filters='notreallyafilter')
        assert_raises(ValueError, self.mkbundle, filters=object())

        # [bug] Specifically test that we can assign ``None``.
        self.mkbundle().filters = None

        # Changing filters after bundle creation is no problem, either.
        b = self.mkbundle()
        assert b.filters == ()
        b.filters = TestFilter
        _assert(b.filters, 1)

        # Assigning the own filter list should change nothing.
        old_filters = b.filters
        b.filters = b.filters
        assert b.filters == old_filters

    def test_depends_assign(self):
        """Test the different ways we can assign dependencies.
        """
        # List of strings.
        b = self.mkbundle(depends=['file1', 'file2'])
        assert len(b.depends) == 2

        # Single string
        b = self.mkbundle(depends='*.sass')
        assert len(b.depends) == 1
        assert b.depends == ['*.sass']

    def test_depends_cached(self):
        """Test that the depends property is cached."""
        self.create_files({'file1.sass': ''})
        b = self.mkbundle(depends=['*.sass'])
        assert len(b.resolve_depends(self.env)) == 1
        self.create_files({'file2.sass': ''})
        assert len(b.resolve_depends(self.env)) == 1


class DummyVersion(Version):
    def __init__(self, version=None):
        self.version = version
    def determine_version(self, bundle, ctx, hunk=None):
        if not self.version:
            raise VersionIndeterminableError('dummy has no version')
        return self.version

class DummyManifest(Manifest):
    def __init__(self, version=None):
        self.log = []
        self.version = version
    def query(self, bundle, ctx):
        return self.version
    def remember(self, *a, **kw):
        self.log.append((a, kw))


class TestVersionFeatures(TempEnvironmentHelper):
    """Test version-specific features: putting the %(version)s placeholder
    in a bundle output filename and the url_expire option, and explicitly
    the resolve_output()/get_version() methods that do the groundwork.
    """

    default_files = {'in': 'foo'}

    def setup(self):
        super(TestVersionFeatures, self).setup()
        self.env.manifest = DummyManifest()
        self.env.versions = DummyVersion()

    def test_build(self):
        """Test the build process creates files with placeholders,
        and stores the version in the manifest.
        """
        self.env.manifest = DummyManifest('manifest')
        self.env.versions = DummyVersion('v1')
        bundle = self.mkbundle('in', output='out-%(version)s')
        bundle.build()

        # The correct output filename has been used
        assert path.basename(bundle.resolve_output()) == 'out-v1'
        assert self.get('out-v1')
        # The version has been logged in the manifest
        assert self.env.manifest.log
        # The version has been cached in an attribute
        assert bundle.version == 'v1'

        self.env.versions.version = 'v999'
        bundle.build(force=True)
        assert path.basename(bundle.resolve_output()) == 'out-v999'
        assert self.get('out-v999')

        # Old file still exists as well. Note that making build() clean
        # up after itself, while certainly possible, is dangerous. In a
        # multi-process, auto_build enabled setup, if no manifest is used,
        # each process would do its own full build.
        assert self.get('out-v1')
        # DummyManifest has two log entries now
        assert len(self.env.manifest.log) == 2

    def test_url(self):
        """Test generating an url for %(version)s outputs."""
        bundle = self.mkbundle('in', output='out-%(version)s')
        self.env.auto_build = False
        bundle.version = 'foo'
        assert bundle.urls() == ['/out-foo']

    def test_version_from_attr(self):
        """If version attr is set, it will be used before anything else."""
        bundle = self.mkbundle('in', output='out-%(version)s')
        self.env.manifest.version = 'manifest'
        self.env.versions.version = 'versions'
        bundle.version = 'attr'
        assert bundle.get_version() == 'attr'
        assert bundle.resolve_output() == self.path('out-attr')

    def test_version_from_manifest(self):
        """The manifest is checked  first for the version."""
        bundle = self.mkbundle('in', output='out-%(version)s')
        self.env.manifest.version = 'manifest'
        self.env.versions.version = 'versions'
        assert bundle.get_version() == 'manifest'
        assert bundle.resolve_output() == self.path('out-manifest')

    def test_version_from_versioner(self):
        """If version is not in manifest, check versioner"""
        bundle = self.mkbundle('in', output='out-%(version)s')
        self.env.manifest.version = None
        self.env.versions.version = 'versions'
        assert bundle.get_version() == 'versions'
        assert bundle.resolve_output() == self.path('out-versions')

    def test_version_not_available(self):
        """If no version in manifest or versioner, error ir raised."""
        bundle = self.mkbundle('in', output='out-%(version)s')
        self.env.manifest.version = None
        self.env.versions.version = None
        assert_raises_regex(
            BundleError, 'dummy has no version', bundle.get_version)
        assert_raises_regex(
            BundleError, 'dummy has no version', bundle.resolve_output)

    def test_get_version_refresh(self):
        """Behaviour of the refresh=True option of get_version().

        This is a specific one, but we want to make sure that it  works, and
        it will not fall back on a bundle.version  attribute that might already
        be set."""
        bundle = self.mkbundle('in', output='out-%(version)s')
        self.env.manifest.version = 'foo'
        bundle.version = 'bar'
        assert bundle.get_version() == 'bar'
        assert bundle.get_version(refresh=True) == 'foo'
        assert bundle.get_version() == 'foo'

        # With no access to a version, refresh=True will raise an error
        # even if a version attribute is already set.
        assert bundle.version == 'foo'
        self.env.manifest.version = None
        self.env.versions.version = None
        assert_raises(BundleError, bundle.get_version, refresh=True)

    def test_url_expire(self):
        """Test the url_expire option.
        """
        self.env.debug = False
        self.env.versions = DummyVersion('foo')
        with_placeholder = self.mkbundle('in', output='out-%(version)s')
        without_placeholder = self.mkbundle('in', output='out')

        # Always add querystring if url_expire=True
        self.env.url_expire = True
        assert len(with_placeholder.urls()) == 1
        assert without_placeholder.urls()[0] == '/out?foo'
        assert with_placeholder.urls()[0] == '/out-foo?foo'

        # Never add querystring if url_expire=False
        self.env.url_expire = False
        assert without_placeholder.urls()[0] == '/out'
        assert with_placeholder.urls()[0] == '/out-foo'

        # Add querystring if no placeholder, if url_expire=None
        self.env.url_expire = None
        assert without_placeholder.urls()[0] == '/out?foo'
        assert with_placeholder.urls()[0] == '/out-foo'

    def test_no_url_expire_with_placeholders(self):
        """[Regression] If the url had placeholders, then url_expire was
        disabled, the placeholder was not resolved in the urls we generated.
        """
        self.env.debug = False
        self.env.url_expire = False
        self.auto_build = False
        self.env.versions = DummyVersion('foo')
        root = self.mkbundle('in', output='out-%(version)s')
        assert root.urls()[0] == '/out-foo'

    def test_story_of_two_envs(self):
        """If an app is served by multiple processes, and auto_build is used,
        if one process rebuilds a bundle, the other one must know (instead of
        continuing to serve the old version.

        For this reason, if auto_build is enabled, the version will always be
        determined anew in every request, rather than using a cached version.
        (This is the reason why get_version() has the refresh=True option).
        """
        # Prepare a manifest and bundle in env1. Use a file manifest
        env1 = self.env
        env1.url_expire = True
        bundle1 = self.mkbundle('in', output='out-%(version)s')

        # Prepare an identical setup, simulating the second process
        env2 = Environment(env1.directory, env1.url)
        env2.config.update(copy.deepcopy(env1.config._dict))
        bundle2  = self.mkbundle('in', output='out-%(version)s')
        bundle2.env = env2

        # Both have auto build enabled, both are using the same manifest
        env1.auto_build = env2.auto_build = True
        env1.manifest = 'file'; env2.manifest = 'file'
        env1.updater = 'timestamp'; env2.updater = 'timestamp'

        # Do the initial build, both envs think they are running the
        # latest version.
        env1.versions.version = bundle1.version = 'old'
        env2.versions.version = bundle2.version = 'old'
        bundle1.build()
        assert env2.updater.needs_rebuild(bundle2, env2) == False

        # At this point, both return the old version in urls
        assert bundle1.urls() ==['/out-old?old']
        assert bundle2.urls() ==['/out-old?old']

        # Now let env1 do an update.
        env1.versions.version = 'new'
        bundle1.build(force=True)
        assert bundle1.urls() == ['/out-new?new']

        # If auto_build is False, env2 will continue to use the old version.
        env2.auto_build = False
        assert bundle2.urls() == ['/out-old?old']
        # However, if auto_build is True, env2 will know the new version.
        # This is because env1 wrote it to the manifest during build.
        env2.auto_build = True
        assert bundle2.get_version() == 'old'    # urls() causes the refresh
        assert bundle2.urls() == ['/out-new?new']
        assert bundle2.get_version() == 'new'

        # The reverse works as well.
        env2.versions.version = 'latest'
        bundle2.build(force=True)
        assert bundle1.urls() == bundle2.urls() == ['/out-latest?latest']


class TestLoadPath(TempEnvironmentHelper):
    """Test the load_path, url_mapping settings, which are basically
    an optional feature.
    """

    def setup(self):
        TempEnvironmentHelper.setup(self)
        self.env.updater = False
        self.env.directory = self.path('dir')
        self.env.debug = True

    def test_single_file(self):
        """Querying a single file (no glob) via the load path."""
        self.env.append_path(self.path('a'))
        self.env.append_path(self.path('b'))
        self.create_files({
            'a/foo': 'a', 'b/foo': 'b', 'b/bar': '42'})

        self.mkbundle('foo', 'bar', output='out').build()
        # Only the first "foo" is found, and "bar" found in second path
        assert self.get('dir/out') == 'a\n42'

    def test_directory_ignored(self):
        """env.directory is ignored with load paths set."""
        self.env.append_path(self.path('a'))
        self.create_files({
            'a/foo': 'a', 'dir/foo': 'dir', 'dir/bar': '42'})

        # The file from the load path is found, not the one from directory
        self.mkbundle('foo', output='out').build()
        assert self.get('dir/out') == 'a'

        # Error because the file from directory is not found
        assert_raises(BundleError, self.mkbundle('bar', output='out').build)

    def test_globbing(self):
        """When used with globbing."""
        self.env.append_path(self.path('a'))
        self.env.append_path(self.path('b'))
        self.create_files({
            'a/foo': 'a', 'b/foo': 'b', 'b/bar': '42'})

        # Returns all files, even duplicate relative filenames in
        # multiple load paths (foo in this case).
        bundle = self.mkbundle('*', output='out')
        assert set(get_all_bundle_files(bundle)) == set([
            self.path('a/foo'), self.path('b/foo'), self.path('b/bar')
        ])

    def test_url_mapping(self):
        """Test mapping the load paths to urls works."""
        self.env.append_path(self.path('a'), '/a')
        self.env.append_path(self.path('b'), '/b')
        self.create_files({
            'a/foo': 'a', 'b/foo': 'b', 'b/bar': '42'})

        assert set(self.mkbundle('*', output='out').urls()) == set([
            '/a/foo', '/b/bar', '/b/foo'
        ])

    def test_entangled_url_mapping(self):
        """A url mapping for a subpath takes precedence over mappings
        that relate to containing folders.
        """
        self.env.append_path(self.path('a'), '/a')
        # Map a subdir to something else
        self.env.url_mapping[self.path('a/sub')] = '/s'
        self.create_files({'a/sub/foo': '42'})
        #  The most inner url mapping, path-wise, takes precedence
        assert self.mkbundle('sub/foo').urls() == ['/s/foo']

    def test_absolute_output_to_loadpath(self):
        """URL generation if output file is written to the load path."""
        self.env.append_path(self.path('a'), '/a')
        self.create_files({'a/foo': 'a'})
        self.env.debug = False
        self.env.url_expire = False
        assert self.mkbundle('*', output=self.path('a/out')).urls() == [
            '/a/out'
        ]

    def test_globbed_load_path(self):
        """The load path itself can contain globs."""
        self.env.append_path(self.path('*'))
        self.create_files({'a/foo': 'a', 'b/foo': 'b', 'dir/bar': 'dir'})

        # With a non-globbed reference
        bundle = self.mkbundle('foo', output='out')
        assert set(get_all_bundle_files(bundle)) == set([
            self.path('a/foo'), self.path('b/foo')
        ])

        # With a globbed reference
        bundle = self.mkbundle('???', output='out')
        assert set(get_all_bundle_files(bundle)) == set([
            self.path('a/foo'), self.path('b/foo'), self.path('dir/bar')
        ])


class TestGlobbing(TempEnvironmentHelper):
    """Test the bundle contents support for patterns.
    """

    default_files = {
        'file1.js': 'foo',
        'file2.js': 'bar',
        'file3.css': 'test'}

    def test_building(self):
        """Globbing works!"""
        self.mkbundle('*.js', output='out').build()
        content = self.get('out').split("\n")
        content.sort()
        assert content == ['bar', 'foo']

    def test_debug_urls(self):
        """In debug mode, the source files matching the pattern are
        returned.
        """
        self.env.debug = True
        urls = self.mkbundle('*.js', output='out').urls()
        urls.sort()
        assert_equal(urls, ['/file1.js', '/file2.js'])

    def test_empty_pattern(self):
        bundle = self.mkbundle('*.xyz', output='out')
        # No error when accessing contents
        bundle.resolve_contents()

    def test_non_pattern_missing_files(self):
        """Ensure that if we specify a non-existant file, it will still
        be returned in the debug urls(), and build() will raise the IOError
        rather than the globbing failing and the bundle being empty
        """
        self.mkbundle('*.js', output='out').build()
        content = self.get('out').split("\n")
        content.sort()
        assert content == ['bar', 'foo']

    def test_recursive_globbing(self):
        """Test recursive globbing using python-glob2.
        """
        try:
            import glob2
        except ImportError:
            raise SkipTest()

        self.create_files({'sub/file.js': 'sub',})
        self.mkbundle('**/*.js', output='out').build()
        content = self.get('out').split("\n")
        content.sort()
        assert content == ['bar', 'foo', 'sub']

    def test_do_not_glob_directories(self):
        """[Regression] Glob should be smart enough not to pick
        up directories."""
        self.create_directories('subdir')
        assert not list(filter(lambda s: 'subdir' in s,
                           get_all_bundle_files(self.mkbundle('*'))))

    def test_glob_exclude_output(self):
        """Never include the output file in the globbinb result.
        """
        self.create_files(['out.js'])
        assert not list(filter(lambda s: 'out.js' in s,
            get_all_bundle_files(self.mkbundle('*', output='out.js'))))


class MockHTTPHandler(HTTPHandler):

    def __init__(self, urls={}):
        self.urls = urls

    def http_open(self, req):
        url = req.get_full_url()
        try:
            content = self.urls[url]
        except KeyError:
            resp = addinfourl(StringIO(""), None, url)
            resp.code = 404
            resp.msg = "OK"
        else:
            resp = addinfourl(StringIO(content), None, url)
            resp.code = 200
            resp.msg = "OK"
        return resp


class TestUrlContents(TempEnvironmentHelper):
    """Test bundles containing a URL.
    """

    def setup(self):
        TempEnvironmentHelper.setup(self)
        mock_opener = build_opener(MockHTTPHandler({
            'http://foo': u'function() {}'}))
        install_opener(mock_opener)

    def test_valid_url(self):
        self.mkbundle('http://foo', output='out').build()
        assert self.get('out') == 'function() {}'

    def test_invalid_url(self):
        """If a bundle contains an invalid url, building will raise an error.
        """
        assert_raises(BuildError,
                      self.mkbundle('http://bar', output='out').build)

    def test_autorebuild_updaters(self):
        # Make sure the timestamp updater can deal with bundles that
        # contain urls. We need to make sure the output file already
        # exists to test this or the updater may simply decide not to
        # run at all.
        self.create_files({'out': 'foo'})
        bundle = self.mkbundle('http://foo', output='out')
        TimestampUpdater().needs_rebuild(bundle, bundle.env)

    def test_pyramid_asset_specs(self):
        """Make sure that pyramid asset specs (in the form of
        package:path) do not pass the url check."""
        self.create_files({'foo:bar/qux': 'test'})
        self.mkbundle('foo:bar/qux', output='out').build()
        assert self.get('out') == 'test'


class TestResolverAPI(TempEnvironmentHelper):
    """The Environment class uses the :class:`Resolver` class to go
    from raw bundle contents to actual paths and urls.

    Subclassing the resolver can be used to do filesystem
    virtualization, and other hackaries.
    """

    def test_resolve_source(self):
        """Test the method is properly used in the build process.
        """
        class MyResolver(self.env.resolver_class):
            def resolve_source(self, ctx, item):
                return path.join(ctx.directory, 'foo')
        self.env.resolver = MyResolver()

        self.create_files({'foo': 'foo'})
        self.mkbundle('bar', output='out').build()
        assert self.get('out') == 'foo'

    def test_depends(self):
        """The bundle dependencies also go through normalization.
        """
        class MyResolver(self.env.resolver_class):
            def resolve_source(self, ctx, item):
                return path.join(ctx.directory, item[::-1])
        self.env.resolver = MyResolver()

        self.create_files(['foo', 'dep', 'out'])
        b = self.mkbundle('oof', depends=('ped',), output='out')

        now = self.setmtime('foo', 'dep', 'out')
        # At this point, no rebuild is required
        assert self.env.updater.needs_rebuild(b, self.env) == False
        # But it is if we update the dependency
        now = self.setmtime('dep', mtime=now+10)
        assert self.env.updater.needs_rebuild(b, self.env) == SKIP_CACHE

    def test_non_string(self):
        """Non-String values can be passed to the bundle, without
        breaking anything (as long as they are resolved to strings
        by _normalize_source_path).

        See https://github.com/miracle2k/webassets/issues/71
        """
        class MyResolver(self.env.resolver_class):
            def resolve_source(self, ctx, item):
                return path.join(ctx.directory, (".".join(item)))
        self.env.resolver = MyResolver()

        self.create_files({'foo.css': 'foo'})
        bundle = self.mkbundle(('foo', 'css'), output='out')

        # Urls
        bundle.urls()
        assert self.get('out') == 'foo'

        # Building
        bundle.build(force=True)
        assert self.get('out') == 'foo'

        # Urls in debug mode
        self.env.debug = True
        urls = bundle.urls()
        assert len(urls) == 1
        assert 'foo' in urls[0]

    def test_resolve_output_to_url_runs_after_version(self):
        """Test that the ``resolve_output_to_url`` method is called after
        the version placeholder is already replaced.

        This is so that implementations can apply url encoding without
        worrying.
        """
        def dummy(ctx, url):
            return url % {'version': 'not the correct version'}
        self.env.resolver.resolve_output_to_url = dummy
        bundle = self.mkbundle('in', output='out-%(version)s')
        self.env.auto_build = False
        bundle.version = 'foo'
        assert bundle.urls() == ['out-foo']
