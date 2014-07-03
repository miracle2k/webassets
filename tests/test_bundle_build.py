"""Tests for the "building" aspect of :class:`Bundle`.

However, building that is associated with a special feature is
more likely` found in `test_bundle_various.py``.
"""


import os
from nose.tools import assert_raises
import pytest
from webassets import Bundle
from webassets.cache import MemoryCache
from webassets.exceptions import BuildError, BundleError
from webassets.filter import Filter
from webassets.test import TempEnvironmentHelper
from webassets.updater import BaseUpdater, SKIP_CACHE, TimestampUpdater

from tests.helpers import noop


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

    def test_empty_bundles(self):
        """Building an empty bundle must be an error. Creating an
        empty output file is not correct, and not doing anything
        is too unpredictable.
        """
        assert_raises(BuildError, self.mkbundle(output='out').build)
        # Even an empty child bundle structure would not bypass this.
        assert_raises(BuildError, self.mkbundle(self.mkbundle(), output='out').build)
        # However, empty child bundles are perfectly valid per se.
        #There just needs to be *something* to build.
        self.mkbundle(self.mkbundle(), 'in1', output='out').build()

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
        from webassets.six import StringIO
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

        self.env.debug = True      # Start with highest level
        self.env.updater = False   # Always rebuild

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
        assert self.get('out') == 'A\nB_'

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
                out.write('%%%'.join([h.data() for h, info in hunks]))
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


class TestMaxDebugLevelFilters(TempEnvironmentHelper):
    """Test how filters are applied when they define a non-default
    ``max_debug_level`` value.
    """

    default_files = {'1': 'foo'}

    # With max_debug_level=True causes merge mode
    # With max_debug_level=None is same as =True
    @pytest.mark.parametrize("level", ['merge', True, None])
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

    # Run once with the rebuild using force=False
    # [Regression] And once using force=True (used to be a bug
    # which caused the change in the dependency to not cause a
    # cache invalidation).
    @pytest.mark.parametrize('rebuild_with_force', [False, True])
    def dependency_refresh_with_cache(self, rebuild_with_force):
        """If a bundle dependency is changed, the cache may not be
        used; otherwise, we'd be using previous build results from
        the cache, where we really need to do a refresh, because,
        for example, an included file has changed.
        """
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
