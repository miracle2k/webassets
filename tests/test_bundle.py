import os
import urllib2
from StringIO import StringIO

from nose.tools import assert_raises, assert_equals
from nose import SkipTest

from webassets import Bundle
from webassets.exceptions import BundleError, BuildError
from webassets.filter import Filter
from webassets.updater import TimestampUpdater, BaseUpdater, SKIP_CACHE
from webassets.cache import MemoryCache

from helpers import TempEnvironmentHelper, noop


class TestBundleConfig(TempEnvironmentHelper):

    def test_init_kwargs(self):
        """We used to silently ignore unsupported kwargs, which can make
        mistakes harder to track down; in particular "filters" vs "filter"
        is confusing. Now we raise an error.
        """
        try:
            Bundle(yaddayada=True)
        except TypeError, e:
            assert "unexpected keyword argument" in ("%s" % e)
        else:
            raise Exception('Expected TypeError not raised')

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


class TestBuild(TempEnvironmentHelper):
    """Test building various bundle structures, in various debug modes.
    """

    def test_simple_bundle(self):
        """Simple bundle, no child bundles, no filters."""
        self.mkbundle('in1', 'in2', output='out').build()
        assert self.get('out') == 'A\nB'

    def test_nested_bundle(self):
        """A nested bundle."""
        self.mkbundle('in1', self.mkbundle('in3', 'in4'), 'in2', output='out').build()
        assert self.get('out') == 'A\nC\nD\nB'

    def test_container_bundle(self):
        """A container bundle.
        """
        self.mkbundle(
            self.mkbundle('in1', output='out1'),
            self.mkbundle('in2', output='out2')).build()
        assert self.get('out1') == 'A'
        assert self.get('out2') == 'B'

    def test_build_return_value(self):
        """build() method returns list of built hunks.
        """
        # Test a simple bundle (single hunk)
        hunks = self.mkbundle('in1', 'in2', output='out').build()
        assert len(hunks) == 1
        assert hunks[0].data() == 'A\nB'

        # Test container bundle (multiple hunks)
        hunks = self.mkbundle(
            self.mkbundle('in1', output='out1'),
            self.mkbundle('in2', output='out2')).build()
        assert len(hunks) == 2
        assert hunks[0].data() == 'A'
        assert hunks[1].data() == 'B'

    def test_nested_bundle_with_skipped_cache(self):
        """[Regression] There was a bug when doing a build with
        an updater that returned SKIP_CACHE, due to passing arguments
        incorrectly.
        """
        class SkipCacheUpdater(BaseUpdater):
            def needs_rebuild(self, *a, **kw):
                return SKIP_CACHE
        self.m.updater = SkipCacheUpdater()
        self.create_files({'out': ''})  # or updater won't come into play
        self.mkbundle('in1', self.mkbundle('in3', 'in4'), 'in2',
                      output='out').build()
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

    def test_deleted_source_files(self):
        """Bundle contents are cached. However, if a file goes missing
        that was included via wildcard, this will not cause any problems
        in subsequent builds.

        If a statically included file goes missing however, the build
        fails.
        """
        self.create_files({'in': 'A', '1.css': '1', '2.css': '2'})
        bundle = self.mkbundle('in', '*.css', output='out')
        bundle.build()
        self.get('out') == 'A12'

        # Delete a wildcard file - we still build fine
        os.unlink(self.path('1.css'))
        bundle.build()
        self.get('out') == 'A1'

        # Delete the static file - now we can't build
        os.unlink(self.path('in'))
        assert_raises(BundleError, bundle.build)

    def test_debug_mode_inherited(self):
        """Make sure that if a bundle sets debug=FOO, that values
        is also used for child bundles.
        """
        b = self.mkbundle(
            'in1',
            self.mkbundle(
                'in2', filters=AppendFilter(':childin', ':childout')),
            output='out', debug='merge',
            filters=AppendFilter(':rootin', ':rootout'))
        b.build()
        # Neither the content of in1 or of in2 have filters applied.
        assert self.get('out') == 'A\nB'

    def test_cannot_build_in_debug_mode(self):
        """While we are in debug mode, bundles refuse to build.

        This is currently a side effect of the implementation, and could
        be designed otherwise: A manual call to build() not caring about
        ``debug=False``.
        However, note that it HAS to care about debug="merge" in any
        case, so maybe the current behavior is the most consistent.
        """
        # Global debug mode
        self.m.debug = True
        b = self.mkbundle('in1', 'in2', output='out')
        assert_raises(BuildError, b.build)

        # Debug mode on bundle itself
        self.m.debug = False
        b = self.mkbundle('in1', 'in2', output='out', debug=True)
        assert_raises(BuildError, b.build)

        # However, if a bundle disables debug directly, it can in fact
        # be built, even if we are globally in debug mode.
        self.m.debug = True
        b = self.mkbundle('in1', 'in2', output='out', debug=False)
        b.build()
        assert self.get('out') == 'A\nB'

    def test_cannot_switch_from_production_to_debug(self):
        """Once we are building a bundle, a child bundle cannot switch
        on debug mode.
        """
        b = self.mkbundle(
            'in1', self.mkbundle('in2', debug=True),
            output='out', debug=False)
        assert_raises(BuildError, b.build)

    def test_merge_does_not_apply_filters(self):
        """Test that while we are in merge mode, the filters are not
        applied.
        """
        self.m.debug = 'merge'
        b = self.mkbundle('in1', 'in2', output='out',
                          filters=AppendFilter(':in', ':out'))
        b.build()
        assert self.get('out') == 'A\nB'

        # Check the reverse - filters are applied when not in merge mode
        b.debug = False
        b.build(force=True)
        assert self.get('out') == 'A:in\nB:in:out'

    def test_switch_from_merge_to_full_debug_false(self):
        """A child bundle may switch on filters while the parent is only
        in merge mode.
        """
        b = self.mkbundle(
            'in1',
            self.mkbundle('in2', debug=False,
                          filters=AppendFilter(':childin', ':childout')),
            output='out', debug='merge',
            filters=AppendFilter(':rootin', ':rootout'))
        b.build()
        # Note how the content of "in1" (A) does not have it's filters
        # applied.
        assert self.get('out') == 'A\nB:childin:rootin:childout'

    def test_invalid_debug_value(self):
        """Test the exception Bundle.build() throws if debug is an
        invalid value."""
        # On the bundle level
        b = self.mkbundle('a', 'b', debug="invalid")
        assert_raises(BundleError, b.build)

        # On the environment level
        self.m.debug = "invalid"
        b = self.mkbundle('a', 'b')
        assert_raises(BundleError, b.build)


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

    def __init__(self, input=None, output=None, unique=True):
        Filter.__init__(self)
        self._input = input
        self._output = output
        self._unique = unique

    def input(self, in_, out, **kw):
        out.write(in_.read())
        if self._input:
            out.write(self._input)

    def output(self, in_, out, **kw):
        out.write(in_.read())
        if self._output:
            out.write(self._output)

    def unique(self):
        if not self._unique:
            return False
        # So we can apply this filter multiple times
        return self._input, self._output


class TestFilters(TempEnvironmentHelper):
    """Test filter application during building.
    """

    default_files = {'1': 'foo', '2': 'foo', '3': 'foo'}

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
        child_bundle = self.mkbundle('1', '2',
                                     filters=AppendFilter(input='-child', unique=False))
        parent_bundle = self.mkbundle(child_bundle, output='out',
                               filters=AppendFilter(input='-parent', unique=False))
        parent_bundle.build()
        assert self.get('out') == 'foo-child\nfoo-child'

    def test_container_bundle_with_filters(self):
        """If a bundle has no output, but filters, those filters are
        passed down to each sub-bundle.
        """
        self.mkbundle(
            Bundle('1', output='out1', filters=()),
            Bundle('2', output='out2', filters=AppendFilter(':childin', ':childout')),
            Bundle('3', output='out3', filters=AppendFilter(':childin', ':childout', unique=False)),
            filters=AppendFilter(':rootin', ':rootout', unique=False)
        ).urls()
        self.p('out1', 'out2', 'out3')
        assert self.get('out1') == 'foo:rootin:rootout'
        assert self.get('out2') == 'foo:childin:rootin:childout:rootout'
        assert self.get('out3') == 'foo:childin:childout'


class TestUpdateAndCreate(TempEnvironmentHelper):
    """Test bundle auto rebuild.
    """

    def setup(self):
        TempEnvironmentHelper.setup(self)

        class CustomUpdater(BaseUpdater):
            allow = True
            def needs_rebuild(self, *a, **kw):
                return self.allow
        self.m.updater = CustomUpdater()

    def test_autocreate(self):
        """If an output file doesn't yet exist, it'll be created (as long
        as automatic building is enabled, anyway).
        """
        self.mkbundle('in1', output='out').build()
        assert self.get('out') == 'A'

    def test_no_autocreate(self):
        """If no updater is given, then the initial build if a previously
        non-existent output file will not happen either.
        """
        self.m.updater = False
        assert_raises(BuildError, self.mkbundle('in1', output='out').build)
        # However, it works fine if force is used
        self.mkbundle('in1', output='out').build(force=True)

    def test_no_updater(self):
        """[Regression] If Environment.updater is set to False/None,
        this won't cause problems during the build.
        """
        self.m.updater = False
        self.create_files({'out': 'old_value'})
        self.mkbundle('in1', output='out').build()
        # And it also means that we don't to auto-rebuilding
        assert self.get('out') == 'old_value'

    def test_no_auto_create_env_via_argument(self):
        """Regression test for a bug that occured when the environment
        was only given via an argument to build(), rather than at Bundle
        __init__ time.
        """
        self.m.updater = False
        assert_raises(BuildError, Bundle('in1', output='out').build, env=self.m)

    def test_updater_says_no(self):
        """If the updater says 'no change', then we never do a build.
        """
        self.create_files({'out': 'old_value'})
        self.m.updater.allow = False
        self.mkbundle('in1', output='out').build()
        assert self.get('out') == 'old_value'

        # force=True overrides the updater
        self.mkbundle('in1', output='out').build(force=True)
        assert self.get('out') == 'A'

    def test_updater_says_yes(self):
        """Test the updater saying we need to update.
        """
        self.create_files({'out': 'old_value'})
        self.m.updater.allow = True
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
        self.m.updater.allow = SKIP_CACHE
        b = self.mkbundle('in1', output='out', filters=noop)
        b.build()
        assert self.get('out') == 'A'
        assert self.m.cache.getc == 0   # cache was not read

        # Test the test: the cache is used with True
        self.m.updater.allow = True
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
        self.m.updater = 'timestamp'
        self.m.cache = False
        self.create_files({'first.sass': 'one'})
        b = self.mkbundle('in1', output='out', depends='*.sass')
        b.build()

        now = self.setmtime('in1', 'first.sass', 'out')
        # At this point, no rebuild is required
        assert self.m.updater.needs_rebuild(b, self.m) == False

        # Create a new file that matches the dependency;
        # make sure it is newer.
        self.create_files({'second.sass': 'two'})
        self.setmtime('second.sass', mtime=now+100)
        # Still no rebuild required though
        assert self.m.updater.needs_rebuild(b, self.m) == False

        # Touch one of the existing files
        self.setmtime('first.sass', mtime=now+200)
        # Do the rebuild that is now required
        # TODO: first.sass is a dependency, because the glob matches
        # the bundle contents as well; As a result, we might check
        # it's timestamp twice. Should something be done about it?
        assert self.m.updater.needs_rebuild(b, self.m) == SKIP_CACHE
        b.build()
        self.setmtime('out', mtime=now+200)

        # Now, touch the new dependency we created - a
        # rebuild is now required.
        self.setmtime('second.sass', mtime=now+300)
        assert self.m.updater.needs_rebuild(b, self.m) == SKIP_CACHE

    def test_dependency_refresh_with_cache(self):
        """If a bundle dependency is changed, the cache may not be
        used; otherwise, we'd be using previous build results from
        the cache, where we really need to do a refresh, because,
        for example, an included file has changed.
        """
        def depends_fake(in_, out):
            out.write(self.get('d.sass'))

        self.m.updater = 'timestamp'
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


class BaseUrlsTester(TempEnvironmentHelper):
    """Baseclass to tes the url generation

    It defines a mock bundle class that intercepts calls to build().
    This allows us to test the Bundle.url() method up to it calling
    into Bundle.build().
    """

    default_files = {'a': '', 'b': '', 'c': '', '1': '', '2': ''}

    def setup(self):
        TempEnvironmentHelper.setup(self)

        self.m.expire = False

        self.build_called = build_called = []
        env = self.m
        class MockBundle(Bundle):
            def __init__(self, *a, **kw):
                Bundle.__init__(self, *a, **kw)
                self.env = env
            def _build(self, *a, **kw):
                build_called.append(self.output)
        self.MockBundle = MockBundle


class TestUrlsCommon(BaseUrlsTester):
    """Other, general tests for the urls() method.
    """
    
    def test_erroneous_debug_value(self):
        """Test the exception Bundle.urls() throws if debug is an invalid
        value."""
        # On the bundle level
        b = self.MockBundle('a', 'b', debug="invalid")
        assert_raises(BundleError, b.urls, env=self.m)

        # On the environment level
        self.m.debug = "invalid"
        b = self.MockBundle('a', 'b')
        assert_raises(BundleError, b.urls, env=self.m)

        # Self-check - this should work if this test works.
        self.MockBundle('a', 'b', debug="merge").urls()

    def test_pass_down_env(self):
        """[Regression] When a root *container* bundle is connected
        to an environment, the child bundles do not have to be.
        """
        child = Bundle('1', '2')
        child.env = None
        root = self.MockBundle(child)
        root.env = self.m
        # Does no longer raise an "unconnected env" exception
        assert root.urls() == ['/1', '/2']


class TestUrlsWithDebugFalse(BaseUrlsTester):
    """Test url generation in production mode - everything is always
    built.
    """

    def test_simple_bundle(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_nested_bundle(self):
        bundle = self.MockBundle('a', self.MockBundle('d', 'childout'), 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_container_bundle(self):
        """A bundle that has only child bundles and does not specify
        an output target of it's own will simply build it's child
        bundles separately.
        """
        bundle = self.MockBundle(
            self.MockBundle('a', output='child1'),
            self.MockBundle('a', output='child2'))
        assert bundle.urls() == ['/child1', '/child2']
        assert len(self.build_called) == 2

    def test_source_bundle(self):
        """If a bundle does neither specify an output target nor any
        filters, it's file are always sourced directly.
        """
        bundle = self.MockBundle('a', self.MockBundle('d', output='childout'))
        assert bundle.urls() == ['/a', '/childout']
        assert len(self.build_called) == 1

    def test_root_bundle_asks_for_merge(self):
        """A bundle explicitly says it wants to be merged, overriding
        the global "debug" setting.

        This makes no difference to the urls that are generated.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug='merge')
        assert_equals(bundle.urls(), ['/childout'])
        assert len(self.build_called) == 1

    def test_root_bundle_asks_for_debug_true(self):
        """A bundle explicitly says it wants to be processed in debug
        mode, overriding the global "debug" setting.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug=True)
        assert_equals(bundle.urls(), ['/1', '/2'])
        assert len(self.build_called) == 0

    def test_root_debug_true_and_child_debug_false(self):
        """The root bundle explicitly says it wants to be processed in
        debug mode, overriding the global "debug" setting, and a child
        bundle asks for debugging to be disabled again.
        """
        bundle = self.MockBundle(
            '1', '2',
            self.MockBundle('a', output='child1', debug=False),
            output='childout', debug=True)
        assert_equals(bundle.urls(), ['/1', '/2', '/child1'])
        assert len(self.build_called) == 1


class TestUrlsWithDebugTrue(BaseUrlsTester):
    """Test url generation in debug mode.
    """

    def setup(self):
        BaseUrlsTester.setup(self)
        self.m.debug = True

    def test_simple_bundle(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert_equals(bundle.urls(), ['/a', '/b', '/c'])
        assert_equals(len(self.build_called), 0)

    def test_nested_bundle(self):
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout'), 'c', output='out')
        assert bundle.urls() == ['/a', '/1', '/2', '/c']
        assert len(self.build_called) == 0

    def test_container_bundle(self):
        """A bundle that has only sub bundles and does not specify
        an output target of it's own.
        """
        bundle = self.MockBundle(
            self.MockBundle('a', output='child1'),
            self.MockBundle('a', output='child2'))
        assert bundle.urls() == ['/a', '/a']
        assert len(self.build_called) == 0

    def test_root_bundle_asks_for_debug_false(self):
        """A bundle explicitly says it wants to be processed with
        debug=False, overriding the global "debug" setting.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug=False)
        assert_equals(bundle.urls(), ['/childout'])
        assert len(self.build_called) == 1

    def test_root_bundle_asks_for_merge(self):
        """A bundle explicitly says it wants to be merged, overriding
        the global "debug" setting.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug='merge')
        assert_equals(bundle.urls(), ['/childout'])
        assert len(self.build_called) == 1

    def test_child_bundle_asks_for_merge(self):
        """A child bundle explicitly says it wants to be processed in
        "merge" mode, overriding the global "debug" setting.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug='merge'),
            'c', output='out')
        assert_equals(bundle.urls(), ['/a', '/childout', '/c'])
        assert len(self.build_called) == 1


class TestUrlsWithDebugMerge(BaseUrlsTester):

    def setup(self):
        BaseUrlsTester.setup(self)
        self.m.debug = 'merge'

    def test_simple_bundle(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_nested_bundle(self):
        bundle = self.MockBundle('a', self.MockBundle('d', 'childout'), 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_child_asks_for_debug_false(self):
        """A child bundle explicitly says it wants to be processed in
        full production mode, with overriding the global "debug" setting.

        This makes no difference to the urls that are generated.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug=False),
            'c', output='out')
        assert_equals(bundle.urls(), ['/out'])
        assert len(self.build_called) == 1


class TestGlobbing(TempEnvironmentHelper):
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
        assert_equals(urls, ['/file1.js', '/file2.js'])

    def test_empty_pattern(self):
        bundle = self.mkbundle('*.xyz', output='out')
        assert_raises(BuildError, bundle.build)

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

        #https://github.com/miracle2k/python-glob2


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


class TestUrlContents(TempEnvironmentHelper):
    """Test bundles containing a URL.
    """

    def setup(self):
        TempEnvironmentHelper.setup(self)
        mock_opener = urllib2.build_opener(MockHTTPHandler({
            'http://foo': 'function() {}'}))
        urllib2.install_opener(mock_opener)

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
