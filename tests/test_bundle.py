from __future__ import with_statement

import copy
import os
from os import path
import urllib2
from StringIO import StringIO

from nose.tools import assert_raises, assert_equals
from nose import SkipTest

from webassets import Bundle
from webassets.bundle import get_all_bundle_files
from webassets.env import Environment
from webassets.exceptions import BundleError, BuildError
from webassets.filter import Filter
from webassets.updater import TimestampUpdater, BaseUpdater, SKIP_CACHE
from webassets.cache import MemoryCache
from webassets.version import Manifest, Version, VersionIndeterminableError

from helpers import (
    TempEnvironmentHelper, TempDirHelper, noop, assert_raises_regexp)


class TestBundleConfig(TempEnvironmentHelper):

    def test_unknown_init_kwargs(self):
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


class TestBuildVarious(TempEnvironmentHelper):
    """Test building various bundle structures, in various different
    circumstances. Generally all things "building" which don't have a
    better place.
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
        self.env.updater = SkipCacheUpdater()
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

    def test_merge_does_not_apply_filters(self):
        """Test that while we are in merge mode, the filters are not
        applied.
        """
        self.env.debug = 'merge'
        b = self.mkbundle('in1', 'in2', output='out',
                          filters=AppendFilter(':in', ':out'))
        b.build()
        assert self.get('out') == 'A\nB'

        # Check the reverse - filters are applied when not in merge mode
        self.env.debug = False
        b.build(force=True)
        assert self.get('out') == 'A:in\nB:in:out'

    def test_auto_create_target_directory(self):
        """A bundle output's target directory is automatically
        created, if it doesn't exist yet.
        """
        self.mkbundle('in1', 'in2', output='out/nested/x/foo').build()
        assert self.get('out/nested/x/foo') == 'A\nB'

    def test_with_custom_output(self):
        """build() method can write to a custom file object."""
        from StringIO import StringIO
        buffer = StringIO()
        self.mkbundle('in1', 'in2', output='out').build(output=buffer)
        assert buffer.getvalue() == 'A\nB'
        assert not self.exists('out')    # file was not written.


class TestBuildWithVariousDebugOptions(TempEnvironmentHelper):
    """Test build behavior with respect to the "debug level", and the various
    ways to set and change the debug level within the bundle hierarchy.
    """

    def test_debug_mode_inherited(self):
        """Make sure that if a bundle sets debug=FOO, that value is also used
        for child bundles.
        """
        self.env.debug = True  # To allow "merge" at all
        b = self.mkbundle(
            'in1',
            self.mkbundle(
                'in2', filters=AppendFilter(':childin', ':childout')),
            output='out', debug='merge',
            filters=AppendFilter(':rootin', ':rootout'))
        b.build()
        # Neither the content of in1 or of in2 have filters applied.
        assert self.get('out') == 'A\nB'

    def test_cannot_increase_debug_level(self):
        """Child bundles cannot increase the debug level.

        If they attempt to, these attempts are silently ignored.
        """
        # False to True has no effect
        self.mkbundle('in1', self.mkbundle('in2', debug=True),
                      output='out', debug=False).build()
        assert self.get('out') == 'A\nB'

        # "merge" to True has no effect
        self.mkbundle(
            'in1', self.mkbundle('in2', debug=True),
            output='out', debug='merge', filters=AppendFilter('_')).build()
        assert self.get('out') == 'A\nB'

        # False to "merge" has no effect
        self.mkbundle(
            'in1', self.mkbundle('in2', debug='merge',
                                 filters=AppendFilter('_')),
            output='out', debug=False).build()
        assert self.get('out') == 'A\nB'

    def test_decreasing_debug_level(self):
        """A child bundle may switch to full production mode (turning on the
        filters), while the parent is only in merge mode.

        The other debug level change (from True to "merge" or from True to
        "False" do not concern us here, and are tested in ``TestUrls*``).
        """
        self.env.debug = 'merge'
        b = self.mkbundle(
            'in1',
            self.mkbundle('in2', debug=False,
                          filters=AppendFilter(':childin', ':childout')),
            output='out', debug='merge',
            filters=AppendFilter(':rootin', ':rootout'))
        b.build()
        # Note how the content of "in1" (A) does not have its filters applied.
        assert self.get('out') == 'A\nB:childin:rootin:childout'

    def test_invalid_debug_value(self):
        """Test exception Bundle.build() throws if debug is an invalid value.
        """
        # On the bundle level
        b = self.mkbundle('a', 'b', output='out', debug="invalid")
        assert_raises(BundleError, b.build)

        # On the environment level
        self.env.debug = "invalid"
        b = self.mkbundle('a', 'b', output='out')
        assert_raises(BundleError, b.build)

    def test_building_in_debug_mode(self):
        """When calling build() while we are in debug mode (debug=False),
        the method builds as if in production mode (debug=False).

        This is a question of API design: If the user calls the method, the
        expectation is clearly for something useful to happen.
        """
        self.env.debug = True
        b = self.mkbundle(
            'in1', 'in2', output='out', filters=AppendFilter('foo'))
        b.build()
        assert self.get('out') == 'Afoo\nBfoo'


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


class TestFilterApplication(TempEnvironmentHelper):
    """Test filter application during building - order, passing down to child
    bundles, that kind of thing.
    """

    default_files = {'1': 'foo', '2': 'foo', '3': 'foo',
                     'a': 'bar', 'b': 'qux'}

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

    def test_input_before_output_nested_unique(self):
        """Same thing as above - a parent input filter is passed done -
        but this time, ensure that duplicate filters are not applied twice.
        """
        child_bundle = self.mkbundle('1', '2',
                                     filters=AppendFilter(input='-child', unique=False))
        parent_bundle = self.mkbundle(child_bundle, output='out',
                               filters=AppendFilter(input='-parent', unique=False))
        parent_bundle.build()
        assert self.get('out') == 'foo-child\nfoo-child'

    def test_input_with_nested_in_merge_mode(self):
        """[Regression] In merge mode, the input filters are not applied for
        child bundles.
        """
        self.env.debug = True  # To allow "merge" at all
        b = self.mkbundle(
            'a',
            self.mkbundle('b',
                          filters=AppendFilter(':childin', ':childout')),
            output='out', filters=AppendFilter(':rootin', ':rootout'),
            debug='merge')
        b.build()
        # Neither the content of in1 or of in2 have filters applied.
        assert self.get('out') == 'bar\nqux'

    def test_input_with_nested_switch_from_merge_to_full_mode(self):
        """A child bundle switches to full production mode (turning on the
        filters), while the parent is only in merge mode. Ensure that in such
        a case input filters declared in the parent are applied in the child
        (and only there).
        """
        self.env.debug = 'merge'
        child_filters = AppendFilter(':childin', ':childout')
        parent_filters = AppendFilter(':rootin', ':rootout')
        b = self.mkbundle(
            'a', self.mkbundle('b', filters=child_filters, debug=False),
            output='out', filters=parent_filters, debug='merge')
        b.build()
        # Note how the content of "in1" (A) does not have its filters applied.
        assert self.get('out') == 'bar\nqux:childin:rootin:childout'

    def test_open_before_input(self):
        """[Regression] Test that if an open filter is used, input filters
        still receive the ``source_path`` kwargs.
        """
        captured_kw = {}
        class TestFilter(Filter):
            def open(self, out, *a, **kw): out.write('foo')
            def input(self, *a, **kw):
                assert not captured_kw
                captured_kw.update(kw)
        self.create_files({'a': '1'})
        self.mkbundle('a', filters=TestFilter, output='out').build()
        # TODO: Could be generalized to test all the other values that
        # each filter method expects to receive. This is currently not
        # done anywhere )though it likely still wouldn't have caught this).
        assert 'source_path' in captured_kw

    def test_duplicate_open_filters(self):
        """Test that only one open() filter can be used.
        """
        # TODO: For performance reasons, this check could possibly be
        # done earlier, when assigning to the filter property. It wouldn't
        # catch all cases involving bundle nesting though.
        class OpenFilter(Filter):
            def open(self, *a, **kw): pass
            def __init__(self, id): Filter.__init__(self); self.id = id
            def id(self): return self.id
        self.create_files(set('xyz'))
        bundle = self.mkbundle(
            'xyz', filters=(OpenFilter('a'), OpenFilter('b')))
        assert_raises(BuildError, bundle.build)

    def test_concat(self):
        """Test the concat() filter type.
        """
        class ConcatFilter(Filter):
            def concat(self, out, hunks, **kw):
                out.write('%%%'.join([h.data() for h in hunks]))
        self.create_files({'a': '1', 'b': '2'})
        self.mkbundle('a', 'b', filters=ConcatFilter, output='out').build()
        assert self.get('out') == '1%%%2'

    # TODO: concat filter child bundle behavior: This should probably be
    # "special", i.e.  the parent concat filter is used, unless overridden
    # in the child.

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
        assert self.get('out1') == 'foo:rootin:rootout'
        assert self.get('out2') == 'foo:childin:rootin:childout:rootout'
        assert self.get('out3') == 'foo:childin:childout'

    def test_max_debug_level_filters(self):
        """Test how filters are applied when they define a non-default
        ``max_debug_level`` value.
        """

        class MaxDebugLevelFilters(TempEnvironmentHelper):
            default_files = {'1': 'foo'}

            def test_with_level(self, level):
                self.env.debug = True  # allows all bundle debug levels
                f = AppendFilter(':in', ':out'); f.max_debug_level = level
                self.mkbundle('1', output='out', filters=f, debug=level).build()
                assert self.get('out') == 'foo:in:out'

            def test_upgrading_affect_on_normal_filters(self):
                """max_debug_level 'merge' upgrade does not cause filters with
                a 'normal' max_debug_value to run. Note: A nested bundle is
                used here, as otherwise the bundle's debug=True would also
                override any upgrades through filter `max_debug_value``
                attributes."""
                self.env.debug = True  # allows all bundle debug levels
                f = AppendFilter(':in_upgr', ':out_upgr')
                f.max_debug_level = None
                g = AppendFilter(':in_def', ':out_def')
                self.mkbundle(Bundle('1', filters=(f, g), debug=True),
                              output='out', debug='merge').build()
                assert self.get('out') == 'foo:in_upgr:out_upgr'

        yield MaxDebugLevelFilters.test_with_level, 'merge'
        # With max_debug_level=True causes merge mode
        yield MaxDebugLevelFilters.test_with_level, True
        # With max_debug_level=None is same as =True
        yield MaxDebugLevelFilters.test_with_level, None

        yield MaxDebugLevelFilters.test_upgrading_affect_on_normal_filters


class TestAutoBuild(TempEnvironmentHelper):
    """Test bundle auto rebuild (which affects the urls() method) and
    generally everything involving the updater (as used by the build() method).
    """

    def setup(self):
        TempEnvironmentHelper.setup(self)

        class CustomUpdater(BaseUpdater):
            allow = True
            def needs_rebuild(self, *a, **kw):
                return self.allow
        self.env.updater = self.updater = CustomUpdater()

    def test_autocreate(self):
        """If an output file doesn't yet exist, it'll be created.
        """
        self.env.auto_build = True
        self.mkbundle('in1', output='out').urls()
        assert self.get('out') == 'A'

    def test_autocreate_with_autobuild_disabled(self):
        """Behavior of urls() and build() interfaces with auto_build
        setting disabled.
        """
        self.env.auto_build = False
        self.env.url_expire = False
        bundle = self.mkbundle('in1', output='out')

        # urls() doesn't cause a build with auto_build = False
        bundle.urls()
        assert not self.exists('out')

        # build() always builds, regardless of auto_build setting.
        # Note: This used to raise an exception, then it was a simple noop,
        # now it does what the name says it'll do.
        bundle.build(force=False)
        assert self.get('out') == 'A'

    def test_no_updater(self):
        """[Regression] If Environment.updater is set to False/None,
        this won't cause problems during the build, and will in fact be the
        equivalent of always passing force=True.
        """
        self.env.updater = False
        self.create_files({'out': 'old_value'})
        self.mkbundle('in1', output='out').build(force=False)
        # Despite force=False we will do a built, because there is in fact no
        # updater that the force argument could disable.
        assert self.get('out') == 'A'

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

        self.env.cache = TestMemoryCache(100)
        self.create_files({'out': 'old_value'})
        self.updater.allow = SKIP_CACHE
        b = self.mkbundle('in1', output='out', filters=noop)
        b.build()
        assert self.get('out') == 'A'
        assert self.env.cache.getc == 0   # cache was not read

        # Test the test: the cache is used with True
        self.updater.allow = True
        b.build()
        assert self.env.cache.getc > 0    # cache was touched

    def test_dependency_refresh(self):
        """This tests a specific behavior of bundle dependencies.
        If they are specified via glob, then that glob is cached
        and only refreshed after a build. The thinking is that in
        those cases for which the depends option was designed, if
        for example a new SASS include file is created, for this
        file to be included, one of the existing files first needs
        to be modified to actually add the include command.
        """
        updater = self.env.updater = TimestampUpdater()
        self.env.cache = False
        self.create_files({'first.sass': 'one'})
        b = self.mkbundle('in1', output='out', depends='*.sass')
        b.build()

        now = self.setmtime('in1', 'first.sass', 'out')
        # At this point, no rebuild is required
        assert updater.needs_rebuild(b, self.env) == False

        # Create a new file that matches the dependency;
        # make sure it is newer.
        self.create_files({'second.sass': 'two'})
        self.setmtime('second.sass', mtime=now+100)
        # Still no rebuild required though
        assert updater.needs_rebuild(b, self.env) == False

        # Touch one of the existing files
        self.setmtime('first.sass', mtime=now+200)
        # Do the rebuild that is now required
        # TODO: first.sass is a dependency, because the glob matches
        # the bundle contents as well; As a result, we might check
        # its timestamp twice. Should something be done about it?
        assert updater.needs_rebuild(b, self.env) == SKIP_CACHE
        b.build()
        self.setmtime('out', mtime=now+200)

        # Now, touch the new dependency we created - a
        # rebuild is now required.
        self.setmtime('second.sass', mtime=now+300)
        assert updater.needs_rebuild(b, self.env) == SKIP_CACHE

    def test_dependency_refresh_with_cache(self):
        """If a bundle dependency is changed, the cache may not be
        used; otherwise, we'd be using previous build results from
        the cache, where we really need to do a refresh, because,
        for example, an included file has changed.
        """
        # Run once with the rebuild using force=False
        yield self._dependency_refresh_with_cache, False
        # [Regression] And once using force=True (used to be a bug
        # which caused the change in the dependency to not cause a
        # cache invalidation).
        yield self._dependency_refresh_with_cache, True

    def _dependency_refresh_with_cache(self, rebuild_with_force):
        # We have to repeat these a lot
        DEPENDENCY = 'dependency.sass'
        DEPENDENCY_SUB = 'dependency_sub.sass'

        # Init a environment with a cache
        self.env.updater = TimestampUpdater()
        self.env.cache = MemoryCache(100)
        self.create_files({
            DEPENDENCY: '-main',
            DEPENDENCY_SUB: '-sub',
            'in': '',
            'in_sub': ''})

        # Create a bundle with a dependency, and a filter which
        # will cause the dependency content to be written. If
        # everything works as it should, a change in the
        # dependency should thus cause the output to change.
        bundle = self.mkbundle(
            'in',
            output='out',
            depends=(DEPENDENCY,),
            filters=lambda in_, out: out.write(in_.read()+self.get(DEPENDENCY)))

        # Additionally, to test how the cache usage of the parent
        # bundle affects child bundles, create a child bundle.
        # This one also writes the final content based on a dependency,
        # but one that is undeclared, so to not override the parent
        # cache behavior, the passing down of which we intend to test.
        #
        # This is a constructed setup so we can test whether the child
        # bundle was using the cache by looking at the output, not
        # something that makes sense in real usage.
        bundle.contents += (self.mkbundle(
            'in_sub',
            filters=lambda in_, out: out.write(self.get(DEPENDENCY_SUB))),)

        # Do an initial build to ensure we have the build steps in
        # the cache.
        bundle.build()
        assert self.get('out') == '\n-sub-main'
        assert self.env.cache.keys

        # Change the dependencies
        self.create_files({DEPENDENCY: '-main12345'})
        self.create_files({DEPENDENCY_SUB: '-subABCDE'})

        # Ensure the timestamps are such that dependency will
        # cause the rebuild.
        now = self.setmtime('out')
        self.setmtime('in', 'in_sub', mtime=now-100)
        self.setmtime(DEPENDENCY, DEPENDENCY_SUB, mtime=now+100)

        # Build again, verify result
        bundle.build(force=rebuild_with_force)
        # The main bundle has always updated (i.e. the cache
        # was invalidated/not used).
        #
        # The child bundle is still using the cache if force=True is
        # used, but will inherit the 'skip the cache' flag from the
        # parent when force=False.
        # There is no reason for this, it's just the way the code
        # currently works, and liable to change in the future.
        if rebuild_with_force:
            assert self.get('out') == '\n-sub-main12345'
        else:
            assert self.get('out') == '\n-subABCDE-main12345'


class BaseUrlsTester(TempEnvironmentHelper):
    """Baseclass to test the url generation

    It defines a mock bundle class that intercepts calls to build().
    This allows us to test the Bundle.url() method up to it calling
    into Bundle.build().
    """

    default_files = {'a': '', 'b': '', 'c': '', '1': '', '2': ''}

    def setup(self):
        TempEnvironmentHelper.setup(self)

        self.env.url_expire = False

        self.build_called = build_called = []
        self.makeurl_called = makeurl_called = []
        env = self.env
        class MockBundle(Bundle):
            def __init__(self, *a, **kw):
                Bundle.__init__(self, *a, **kw)
                self.env = env
            def _build(self, *a, **kw):
                build_called.append(self.output)
            def _make_url(self, *a, **kw):
                makeurl_called.append(self.output)
                return Bundle._make_url(self, *a, **kw)
        self.MockBundle = MockBundle


class TestUrlsVarious(BaseUrlsTester):
    """Other, general tests for the urls() method.

    The TestUrls()* classes test the logic behind urls(). The ``url_expire``
    option is part of ``TestVersionFeatures``.
    """

    def test_erroneous_debug_value(self):
        """Test the exception Bundle.urls() throws if debug is an invalid
        value."""
        # On the bundle level
        b = self.MockBundle('a', 'b', debug="invalid")
        assert_raises(BundleError, b.urls, env=self.env)

        # On the environment level
        self.env.debug = "invalid"
        b = self.MockBundle('a', 'b')
        assert_raises(BundleError, b.urls, env=self.env)

        # Self-check - this should work if this test works.
        self.env.debug = True  # valid again
        self.MockBundle('a', 'b', debug="merge").urls()

    def test_pass_down_env(self):
        """[Regression] When a root *container* bundle is connected
        to an environment, the child bundles do not have to be.
        """
        child = Bundle('1', '2')
        child.env = None
        root = self.MockBundle(child)
        root.env = self.env
        # Does no longer raise an "unconnected env" exception
        assert root.urls() == ['/1', '/2']

    def test_invalid_source_file(self):
        """If a source file is missing, an error is raised even when rendering
        the urls (as opposed to just outputting the url to the missing file
        (this is cached and only done once).

        It's helpful for debugging (in particular when rewriting takes place by
        things like the django-staticfiles extension, or Flask's blueprints).
        """
        self.env.debug = True
        bundle = self.mkbundle('non-existent-file', output="out")
        assert_raises(BundleError, bundle.urls)

    def test_filters_in_debug_mode(self):
        """Test that if a filter is used which runs in debug mode, the bundle
        is forcibly merged (unless overridden)
        """
        self.env.debug = True
        test_filter = AppendFilter()
        bundle = self.MockBundle('a', filters=test_filter, output='out')

        # We get the source files...
        assert bundle.urls() == ['/a']
        assert len(self.build_called) == 0

        # ...until the filter is switched to 'always run'
        test_filter.max_debug_level = None
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

        # An explicit bundle debug=True overrides the behavior.
        bundle.debug = True
        assert bundle.urls() == ['/a']
        assert len(self.build_called) == 1  # no change

    def test_external_refs(self):
        """If a bundle contains absolute paths outside of the
        media directory, to generate a url they are copied in.
        """
        try:
            from nose.tools import assert_regexp_matches
        except ImportError:
            raise SkipTest("Assertion method only present in 2.7+")
        self.env.debug = True
        with TempDirHelper() as h:
            h.create_files(['foo.css'])
            bundle = self.mkbundle(h.path('foo.css'))
            urls = bundle.urls()
            assert len(urls) == 1
            assert_regexp_matches(urls[0], r'/webassets-external/\d*_foo.css')


class TestUrlsWithDebugFalse(BaseUrlsTester):
    """Test url generation in production mode - everything is always built.
    """

    def test_simple_bundle(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_nested_bundle(self):
        bundle = self.MockBundle(
            'a', self.MockBundle('d', 'childout'), 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_container_bundle(self):
        """A bundle that has only child bundles and does not specify
        an output target of its own will simply build its child
        bundles separately.
        """
        bundle = self.MockBundle(
            self.MockBundle('a', output='child1'),
            self.MockBundle('a', output='child2'))
        assert bundle.urls() == ['/child1', '/child2']
        assert len(self.build_called) == 2

    def test_source_bundle(self):
        """If a bundle does neither specify an output target nor any
        filters, its file are always sourced directly.
        """
        bundle = self.MockBundle('a', self.MockBundle('d', output='childout'))
        assert bundle.urls() == ['/a', '/childout']
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_merge(self):
        """A bundle explicitly says it wants to be merged, wanting to override
        the  global "debug=False" setting. This is ineffectual (and anyway
        does not affect url generation).
        """
        bundle = self.MockBundle('1', '2', output='childout', debug='merge')
        assert_equals(bundle.urls(), ['/childout'])
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_debug_true(self):
        """A bundle explicitly says it wants to be processed in debug
        mode, wanting overriding the global "debug=False" setting. This is
        ineffectual.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug=True)
        assert_equals(bundle.urls(), ['/childout'])
        assert len(self.build_called) == 1

    def test_root_debug_true_and_child_debug_false(self):
        """The root bundle explicitly says it wants to be processed in
        debug mode, overriding the global "debug" setting, and a child
        bundle asks for debugging to be disabled again.

        None of this has any effect, since Environment.debug=False.
        """
        bundle = self.MockBundle(
                '1', '2',
                self.MockBundle('a', output='child1', debug=False),
                output='rootout', debug=True)
        assert_equals(bundle.urls(), ['/rootout'])


class TestUrlsWithDebugTrue(BaseUrlsTester):
    """Test url generation in debug mode.
    """

    def setup(self):
        BaseUrlsTester.setup(self)
        self.env.debug = True

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
        an output target of its own.
        """
        bundle = self.MockBundle(
            self.MockBundle('a', output='child1'),
            self.MockBundle('a', output='child2'))
        assert bundle.urls() == ['/a', '/a']
        assert len(self.build_called) == 0

    def test_url_source(self):
        """[Regression] Test a Bundle that contains a source URL.
        """
        bundle = self.MockBundle('http://test.de', output='out')
        assert_equals(bundle.urls(), ['http://test.de'])
        assert_equals(len(self.build_called), 0)

        # This is the important test. It proves that the url source
        # was handled separately, and not processed like any other
        # source file, which would be passed through makeurl().
        # This is a bit convoluted to test because the code that
        # converts a bundle content into an url operates just fine
        # on a url source, so there is no easy other way to determine
        # whether the url source was treated special.
        assert_equals(len(self.makeurl_called), 0)

    def test_root_bundle_switching_to_debug_false(self):
        """A bundle explicitly says it wants to be processed with
        debug=False, overriding the global "debug=True" setting.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug=False)
        assert_equals(bundle.urls(), ['/childout'])
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_merge(self):
        """A bundle explicitly says it wants to be merged, overriding
        the global "debug=True" setting.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug='merge')
        assert_equals(bundle.urls(), ['/childout'])
        assert len(self.build_called) == 1

    def test_child_bundle_switching(self):
        """A child bundle explicitly says it wants to be processed in
        "merge" mode, overriding the global "debug=True" setting, with the
        root bundle not having an opinion.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug='merge'),
            'c', output='out')
        assert_equals(bundle.urls(), ['/a', '/childout', '/c'])
        assert len(self.build_called) == 1


class TestUrlsWithDebugMerge(BaseUrlsTester):

    def setup(self):
        BaseUrlsTester.setup(self)
        self.env.debug = 'merge'

    def test_simple_bundle(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_nested_bundle(self):
        bundle = self.MockBundle('a', self.MockBundle('d', 'childout'), 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_child_bundle_switching_to_debug_false(self):
        """A child bundle explicitly says it wants to be processed in
        full production mode, with overriding the global "debug" setting.

        This makes no difference to the urls that are generated.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug=False),
            'c', output='out')
        assert_equals(bundle.urls(), ['/out'])
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_debug_true(self):
        """A bundle explicitly says it wants to be processed in debug mode,
        overriding the global ``debug=merge"`` setting. This is ineffectual.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug=True),
            'c', output='out')
        assert_equals(bundle.urls(), ['/out'])
        assert len(self.build_called) == 1


class DummyVersion(Version):
    def __init__(self, version=None):
        self.version = version
    def determine_version(self, bundle, env, hunk=None):
        if not self.version:
            raise VersionIndeterminableError('dummy has no version')
        return self.version

class DummyManifest(Manifest):
    def __init__(self, version=None):
        self.log = []
        self.version = version
    def query(self, bundle, env):
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
        assert_raises_regexp(
            BundleError, 'dummy has no version', bundle.get_version)
        assert_raises_regexp(
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
        self.env.debug = True
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

    def test_do_not_glob_directories(self):
        """[Regression] Glob should be smart enough not to pick
        up directories."""
        self.create_directories('subdir')
        assert not filter(lambda s: 'subdir' in s,
                           get_all_bundle_files(self.mkbundle('*')))

    def test_glob_exclude_output(self):
        """Never include the output file in the globbinb result.
        """
        self.create_files(['out.js'])
        assert not filter(lambda s: 'out.js' in s,
            get_all_bundle_files(self.mkbundle('*', output='out.js')))


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

    def test_pyramid_asset_specs(self):
        """Make sure that pyramid asset specs (in the form of
        package:path) do not pass the url check."""
        self.create_files({'foo:bar/qux': 'test'})
        self.mkbundle('foo:bar/qux', output='out').build()
        assert self.get('out') == 'test'


class TestNormalizeSourcePath(TempEnvironmentHelper):
    """The Environment class allows overriding a
    _normalize_source_path() method, which can be used to
    support some simple filesystem virtualization, and other
    hackaries.
    """

    def test(self):
        """Test the method is properly used in the build process.
        """
        class MyEnv(self.env.__class__):
            def _normalize_source_path(self, path):
                return self.abspath("foo")
        self.env.__class__ = MyEnv
        self.create_files({'foo': 'foo'})
        self.mkbundle('bar', output='out').build()
        assert self.get('out') == 'foo'

    def test_non_string(self):
        """Non-String values can be passed to the bundle, without
        breaking anything (as long as they are resolved to strings
        by _normalize_source_path).

        See https://github.com/miracle2k/webassets/issues/71
        """
        class MyEnv(self.env.__class__):
            def _normalize_source_path(self, path):
                return self.abspath(".".join(path))
            def absurl(self, url):
                return url[0]
        self.env.__class__ = MyEnv
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

    def test_depends(self):
        """The bundle dependencies also go through
        normalization.
        """
        class MyEnv(self.env.__class__):
            def _normalize_source_path(self, path):
                return self.abspath(path[::-1])
        self.env.__class__ = MyEnv
        self.create_files(['foo', 'dep', 'out'])
        b = self.mkbundle('oof', depends=('ped',), output='out')

        now = self.setmtime('foo', 'dep', 'out')
        # At this point, no rebuild is required
        assert self.env.updater.needs_rebuild(b, self.env) == False
        # But it is if we update the dependency
        now = self.setmtime('dep', mtime=now+10)
        assert self.env.updater.needs_rebuild(b, self.env) == SKIP_CACHE
