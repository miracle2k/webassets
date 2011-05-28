import urllib2
from StringIO import StringIO

from nose.tools import assert_raises, assert_equals
from nose import SkipTest
from test.test_support import check_warnings

from webassets import Bundle
from webassets.bundle import BuildError
from webassets.filter import Filter
from webassets.updater import TimestampUpdater, BaseUpdater, SKIP_CACHE
from webassets.cache import MemoryCache

from helpers import BuildTestHelper, noop


class TestBundleConfig(BuildTestHelper):

    def test_init_kwargs(self):
        """We used to silently ignore unsupported kwargs, which can make
        mistakes harder to track down; in particular "filters" vs "filter"
        is confusing. Now we raise an error.
        """
        assert_raises(TypeError, Bundle, yaddayada=True)

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
        assert b.filters is ()
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
        assert len(b.resolve_depends(self.m)) == 1
        self.create_files({'file2.sass': ''})
        assert len(b.resolve_depends(self.m)) == 1


class TestVersionSystemDeprecations(BuildTestHelper):
    """With the introduction of the ``Environment.version`` system,
    some functionality has been deprecated.
    """

    def test_expire_option(self):
        # Assigning to the expire option raises a deprecation warning
        with check_warnings(("", DeprecationWarning)) as w:
            self.m.expire = True
        with check_warnings(("", DeprecationWarning)):
            self.m.config['expire'] = True
        # Reading the expire option raises a warning also.
        with check_warnings(("", DeprecationWarning)):
            x = self.m.expire
        with check_warnings(("", DeprecationWarning)):
            x = self.m.config['expire']
        
    def test_updater_option(self):
        # Assigning to the updater option raises a deprecation warning
        with check_warnings(("", DeprecationWarning)):
            self.m.updater = True
        with check_warnings(("", DeprecationWarning)):
            self.m.config['updater'] = True
        # Reading the updater option raises a warning also.
        with check_warnings(("", DeprecationWarning)):
            x = self.m.updater
        with check_warnings(("", DeprecationWarning)):
            x = self.m.config['updater']

    def test_expire_option_passthrough(self):
        """While "expire" no longer exists, we attempt to provide an
        emulation."""
        with check_warnings(("", DeprecationWarning)):
            # Read
            self.m.url_expire = False
            assert self.m.expire == False
            self.m.url_expire = True
            assert self.m.expire == 'querystring'
            # Write
            self.m.expire = False
            assert self.m.url_expire == False
            self.m.expire = 'querystring'
            assert self.m.url_expire == True

    def test_updater_option_passthrough(self):
        """While "updater" no longer exists, we attempt to provide an
        emulation."""
        with check_warnings(("", DeprecationWarning)):
            # Read
            self.m.auto_build = False
            assert self.m.updater == False
            self.m.auto_build = True
            assert self.m.updater == 'timestamp'
            # Write
            self.m.updater = False
            assert self.m.auto_build == False
            self.m.updater = 'timestamp'
            assert self.m.auto_build == True


class TestBuild(BuildTestHelper):
    """Test building various bundle structures.
    """

    def test_simple(self):
        """Simple bundle, no subbundles, no filters."""
        self.mkbundle('in1', 'in2', output='out').build()
        assert self.get('out') == 'A\nB'

    def test_nested(self):
        """A nested bundle."""
        self.mkbundle('in1', self.mkbundle('in3', 'in4'), 'in2', output='out').build()
        assert self.get('out') == 'A\nC\nD\nB'

    def test_no_output_error(self):
        """A bundle without an output configured cannot be built.
        """
        assert_raises(BuildError, self.mkbundle('in1', 'in2').build)

    def test_empty_bundle_error(self):
        """An empty bundle cannot be built.
        """
        assert_raises(BuildError, self.mkbundle(output='out').build)
        # That is true even for child bundles
        assert_raises(BuildError, self.mkbundle(self.mkbundle(), 'in1', output='out').build)

    def test_rebuild(self):
        """Regression test for a bug that occurred when a bundle
        was built a second time since Bundle.get_files() did
        not return absolute filenames."""
        self.mkbundle('in1', 'in2', output='out').build()
        assert self.get('out') == 'A\nB'
        self.mkbundle('in1', 'in2', output='out').build()
        assert self.get('out') == 'A\nB'


class ReplaceFilter(Filter):
    """Filter that does a simple string replacement.
    """

    def __init__(self, input=(None, None), output=(None, None)):
        Filter.__init__(self)
        self._input_from, self._input_to = input
        self._output_from, self._output_to = output

    def input(self, in_, out, **kw):
        if self._input_from:
            out.write(in_.read().replace(self._input_from, self._input_to))
        else:
            out.write(in_.read())

    def output(self, in_, out, **kw):
        if self._output_from:
            out.write(in_.read().replace(self._output_from, self._output_to))
        else:
            out.write(in_.read())

    def unique(self):
        # So we can apply this filter multiple times
        return self._input_from, self._output_from


class AppendFilter(Filter):
    """Filter that simply appends stuff.
    """

    def __init__(self, input=None, output=None):
        Filter.__init__(self)
        self._input = input
        self._output = output

    def input(self, in_, out, **kw):
        out.write(in_.read())
        if self._input:
            out.write(self._input)

    def output(self, in_, out, **kw):
        out.write(in_.read())
        if self._output:
            out.write(self._output)

    # Does not define unique(), can only be applied once!


class TestFilters(BuildTestHelper):
    """Test filter application during building.
    """

    default_files = {'1': 'foo', '2': 'foo'}

    def test_input_before_output(self):
        """Ensure that input filters are applied, and that they are applied
        before an output filter gets to say something.
        """
        self.mkbundle('1', '2', output='out', filters=ReplaceFilter(
            input=('foo', 'input was here'), output=('foo', 'output was here'))).build()
        assert self.get('out') == 'input was here\ninput was here'

    def test_output_after_input(self):
        """Ensure that output filters are applied, and that they are applied
        after input filters did their job.
        """
        self.mkbundle('1', '2', output='out', filters=ReplaceFilter(
            input=('foo', 'bar'), output=('bar', 'output was here'))).build()
        assert self.get('out') == 'output was here\noutput was here'

    def test_input_before_output_nested(self):
        """Ensure that when nested bundles are used, a parent bundles
        input filters are applied before a child bundles output filter.
        """
        child_bundle_with_output_filter = self.mkbundle('1', '2',
                filters=ReplaceFilter(output=('foo', 'output was here')))
        parent_bundle_with_input_filter = self.mkbundle(child_bundle_with_output_filter,
                output='out',
                filters=ReplaceFilter(input=('foo', 'input was here')))
        parent_bundle_with_input_filter.build()
        assert self.get('out') == 'input was here\ninput was here'

    def test_input_before_output_nested_merged(self):
        """Same thing as above - a parent input filter is passed done -
        but this time, ensure that duplicate filters are not applied twice.
        """
        child_bundle = self.mkbundle('1', '2', filters=AppendFilter(input='-child'))
        parent_bundle = self.mkbundle(child_bundle, output='out',
                               filters=AppendFilter(input='-parent'))
        parent_bundle.build()
        assert self.get('out') == 'foo-child\nfoo-child'

    def test_no_filters_option(self):
        """If ``no_filters`` is given, then filters are simply not applied.
        """
        child_filter = AppendFilter(output='-child:out', input='-child:in')
        parent_filter = AppendFilter(output='-parent:out', input='-parent:in')
        self.mkbundle('1', self.mkbundle('2', filters=child_filter),
               filters=parent_filter, output='out').build(no_filters=True)
        assert self.get('out') == 'foo\nfoo'


class TestUpdateAndCreate(BuildTestHelper):
    """Test bundle auto rebuild.
    """

    def setup(self):
        BuildTestHelper.setup(self)

        class CustomUpdater(BaseUpdater):
            allow = True
            def needs_rebuild(self, *a, **kw):
                return self.allow
        self.m.versioner.updater = self.updater = CustomUpdater()

    def test_autocreate(self):
        """If an output file doesn't yet exist, it'll be created (as long
        as automatic building is enabled, anyway).
        """
        self.m.auto_build = True
        self.mkbundle('in1', output='out').build()
        assert self.get('out') == 'A'

    def test_no_auto_create(self):
        """If auto_build is disabled, then the initial build of a
        previously non-existent output file will not happen either.
        """
        self.m.auto_build = False
        assert_raises(BuildError, self.mkbundle('in1', output='out').build)
        # However, it works fine if force is used
        self.mkbundle('in1', output='out').build(force=True)

    def test_no_auto_create_env_via_argument(self):
        """Regression test for a bug that occured when the environment
        was only given via an argument to build(), rather than at Bundle
        __init__ time.
        """
        self.m.auto_build = False
        assert_raises(BuildError, Bundle('in1', output='out').build, env=self.m)

    def test_updater_says_no(self):
        """If the updater says 'no change', then we never do a build.
        """
        self.create_files({'out': 'old_value'})
        self.updater.allow = False
        self.mkbundle('in1', output='out').build()
        assert self.get('out') == 'old_value'

        # force=True overrides the updater
        self.mkbundle('in1', output='out').build(force=True)
        assert self.get('out') == 'A'

    def test_updater_says_yes(self):
        """Test the updater saying we need to update.
        """
        self.create_files({'out': 'old_value'})
        self.updater.allow = True
        self.mkbundle('in1', output='out').build()
        assert self.get('out') == 'A'

    def test_updater_says_skip_cache(self):
        """Test the updater saying we need to update without relying
        on the cache.
        """
        class TestMemoryCache(MemoryCache):
            getc = 0
            def get(self, key):
                self.getc += 1
                return MemoryCache.get(self, key)

        self.m.cache = TestMemoryCache(100)
        self.create_files({'out': 'old_value'})
        self.updater.allow = SKIP_CACHE
        b = self.mkbundle('in1', output='out', filters=noop)
        b.build()
        assert self.get('out') == 'A'
        assert self.m.cache.getc == 0   # cache was not read

        # Test the test: the cache is used with True
        self.updater.allow = True
        b.build()
        assert self.m.cache.getc > 0    # cache was touched

    def test_dependency_refresh(self):
        """This tests a specific behavior of bundle dependencies.
        If they are specified via glob, then that glob is cached
        and only refreshed after a build. The thinking is that in
        those cases for which the depends option was designed, if
        for example a new SASS include file is created, for this
        file to be included, one of the existing files first needs
        to be modified to actually add the include command.
        """
        updater = self.m.versioner.updater = TimestampUpdater()
        self.m.cache = False
        self.create_files({'first.sass': 'one'})
        b = self.mkbundle('in1', output='out', depends='*.sass')
        b.build()

        now = self.setmtime('in1', 'first.sass', 'out')
        # At this point, no rebuild is required
        assert updater.needs_rebuild(b, self.m) == False

        # Create a new file that matches the dependency;
        # make sure it is newer.
        self.create_files({'second.sass': 'two'})
        self.setmtime('second.sass', mtime=now+100)
        # Still no rebuild required though
        assert updater.needs_rebuild(b, self.m) == False

        # Touch one of the existing files
        self.setmtime('first.sass', mtime=now+200)
        # Do the rebuild that is now required
        # TODO: first.sass is a dependency, because the glob matches
        # the bundle contents as well; As a result, we might check
        # it's timestamp twice. Should something be done about it?
        assert updater.needs_rebuild(b, self.m) == SKIP_CACHE
        b.build()
        self.setmtime('out', mtime=now+200)

        # Now, touch the new dependency we created - a
        # rebuild is now required.
        self.setmtime('second.sass', mtime=now+300)
        assert updater.needs_rebuild(b, self.m) == SKIP_CACHE

    def test_dependency_refresh_with_cache(self):
        """If a bundle dependency is changed, the cache may not be
        used; otherwise, we'd be using previous build results from
        the cache, where we really need to do a refresh, because,
        for example, an included file has changed.
        """
        def depends_fake(in_, out):
            out.write(self.get('d.sass'))

        self.m.versioner.updater = TimestampUpdater()
        self.m.cache = MemoryCache(100)
        self.create_files({'d.sass': 'initial', 'in': ''})
        bundle = self.mkbundle('in', output='out', depends=('*.sass',),
                               filters=depends_fake)

        # Do an initial build to ensure we have the build steps in
        # the cache.
        bundle.build()
        assert self.get('out') == 'initial'
        assert self.m.cache.keys

        # Change the dependency
        self.create_files({'d.sass': 'new-value-12345'})
        # Ensure the timestamps are such that dependency will
        # cause the rebuild.
        now = self.setmtime('out')
        self.setmtime('in', mtime=now-100)
        self.setmtime('d.sass', mtime=now+100)

        # Build again, verify result
        bundle.build()
        assert self.get('out') == 'new-value-12345'


class BaseUrlsTester(BuildTestHelper):
    """Test the url generation.
    """

    default_files = {}

    def setup(self):
        BuildTestHelper.setup(self)

        self.m.url_expire = False

        self.files_built = files_built = []
        self.no_filter_values = no_filter_values = []
        env = self.m
        class MockBundle(Bundle):
            def __init__(self, *a, **kw):
                Bundle.__init__(self, *a, **kw)
                self.env = env
            def build(self, *a, **kw):
                if not self.output:
                    raise BuildError('no output')
                files_built.append(self.output)
                no_filter_values.append(kw.get('no_filters', False))
        self.MockBundle = MockBundle


class TestUrlsProduction(BaseUrlsTester):
    """Test url generation in production mode - everything is always
    built.
    """

    def test_simple(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.files_built) == 1

    def test_nested(self):
        bundle = self.MockBundle('a', self.MockBundle('d', 'childout'), 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.files_built) == 1

    def test_container_bundle(self):
        """A bundle that has only sub bundles and does not specify
        an output target of it's own will simply build it's child
        bundles separately.
        """
        bundle = self.MockBundle(
            self.MockBundle('a', output='child1'),
            self.MockBundle('a', output='child2'))
        assert bundle.urls() == ['/child1', '/child2']
        assert len(self.files_built) == 2

    def test_container_bundle_with_filters(self):
        """If a bundle has no output, but filters, those filters are
        passed down to each sub-bundle.
        """
        # TODO: This still needs to be implemented, but I'm unsure
        # right now if it's really the behavior I want.
        raise SkipTest()

    def test_source_bundle(self):
        """If a bundle does neither specify an output target nor any
        filters, it's file are always sourced directly.
        """
        bundle = self.MockBundle('a', self.MockBundle('d', output='childout'))
        print bundle.urls()
        assert bundle.urls() == ['/a', '/childout']

    def test_require_output(self):
        """You can misconfigure a bundle if you specify files, filters,
        but do not give an output target.
        """
        bundle = self.MockBundle('a', filters='cssmin')
        assert_raises(BuildError, bundle.urls)


class TestUrlsDebug(BaseUrlsTester):
    """Test url generation in debug mode."""

    def setup(self):
        BaseUrlsTester.setup(self)

        self.m.debug = True
        self.m.url = ''

    def test_simple(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert_equals(bundle.urls(), ['/a', '/b', '/c'])
        assert_equals(len(self.files_built), 0)

    def test_nested(self):
        bundle = self.MockBundle('a', self.MockBundle('1', '2', output='childout'), 'c', output='out')
        assert bundle.urls() == ['/a', '/1', '/2', '/c']
        assert len(self.files_built) == 0

    def test_root_bundle_merge(self):
        """The root bundle says it wants to be merged even in debug mode.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug='merge')
        assert_equals(bundle.urls(), ['/childout'])
        assert len(self.files_built) == 1
        assert self.no_filter_values == [True]

    def test_child_bundle_merge(self):
        """A child bundle says it wants to be merged even when in debug mode.
        """
        bundle = self.MockBundle('a',
                                 self.MockBundle('1', '2', output='childout', debug='merge'),
                                 'c', output='out')
        assert_equals(bundle.urls(), ['/a', '/childout', '/c'])
        assert len(self.files_built) == 1
        assert self.no_filter_values == [True]

    def test_child_bundle_filter(self):
        """A child bundle says it not only wants to be merged, but also
        have the filters applied, when in debug mode.
        """
        bundle = self.MockBundle('a',
                                 self.MockBundle('1', '2', output='childout', debug=False),
                                 'c', output='out')
        assert_equals(bundle.urls(), ['/a', '/childout', '/c'])
        assert len(self.files_built) == 1
        assert self.no_filter_values == [False]

    def test_default_to_merge(self):
        """The global ASSETS_DEBUG setting tells us to at least merge in
        debug mode.
        """
        self.m.debug = 'merge'
        bundle = self.MockBundle('1', '2', output='childout')
        assert_equals(bundle.urls(), ['/childout'])
        assert len(self.files_built) == 1
        assert self.no_filter_values == [True]


class TestGlobbing(BuildTestHelper):
    """Test the bundle contents support for patterns.
    """

    default_files = {'file1.js': 'foo', 'file2.js': 'bar', 'file3.css': 'test'}

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
        self.m.debug = True
        urls = self.mkbundle('*.js', output='out').urls()
        urls.sort()
        assert urls == ['/file1.js', '/file2.js']

    def test_empty_pattern(self):
        bundle = self.mkbundle('*.xyz', output='out')
        assert_raises(BuildError, bundle.build)

    def test_non_pattern_missing_files(self):
        """Ensure that if we specify a non-existant file, it will still
        be returned in the debug urls(), and build() will raise the IOError
        rathern than the globbing failing and the bundle being empty
        """
        self.mkbundle('*.js', output='out').build()
        content = self.get('out').split("\n")
        content.sort()
        assert content == ['bar', 'foo']


class MockHTTPHandler(urllib2.HTTPHandler):

    def __init__(self, urls={}):
        self.urls = urls

    def http_open(self, req):
        url = req.get_full_url()
        try:
            content = self.urls[url]
        except KeyError:
            resp = urllib2.addinfourl(StringIO(""), None, url)
            resp.code = 404
            resp.msg = "OK"
        else:
            resp = urllib2.addinfourl(StringIO(content), None, url)
            resp.code = 200
            resp.msg = "OK"
        return resp


class TestUrlContents(BuildTestHelper):
    """Test bundles containing a URL.
    """

    def setup(self):
        BuildTestHelper.setup(self)
        mock_opener = urllib2.build_opener(MockHTTPHandler({
            'http://foo': 'function() {}'}))
        urllib2.install_opener(mock_opener)

    def test_valid_url(self):
        self.mkbundle('http://foo', output='out').build()
        assert self.get('out') == 'function() {}'

    def test_invalid_url(self):
        """If a bundle contains an invalid url, building will raise an error.
        """
        assert_raises(urllib2.URLError,
                      self.mkbundle('http://bar', output='out').build)

    def test_autorebuild_updaters(self):
        # Make sure the timestamp updater can deal with bundles that
        # contain urls. We need to make sure the output file already
        # exists to test this or the updater may simply decide not to
        # run at all.
        self.create_files({'out': 'foo'})
        bundle = self.mkbundle('http://foo', output='out')
        TimestampUpdater().needs_rebuild(bundle, bundle.env)
