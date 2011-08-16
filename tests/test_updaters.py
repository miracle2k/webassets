import os, time
from nose.tools import assert_raises
from webassets import Environment, Bundle
from webassets.exceptions import BundleError
from webassets.updater import TimestampUpdater, BundleDefUpdater, SKIP_CACHE
from webassets.cache import MemoryCache
from helpers import TempEnvironmentHelper


class TestBundleDefBaseUpdater:
    """Test the updater which caches bundle definitions to determine
    changes.
    """

    def setup(self):
        self.env = Environment(None, None)  # we won't create files
        self.env.cache = MemoryCache(capacity=100)
        self.bundle = Bundle(output="target")
        self.updater = BundleDefUpdater()

    def test_no_rebuild_required(self):
        # Fake an initial build
        self.updater.build_done(self.bundle, self.env)
        # without any changes, no rebuild is required
        assert self.updater.needs_rebuild(self.bundle, self.env) == False

        # Build of another bundle won't change that, i.e. we use the
        # correct caching key for each bundle.
        bundle2 = Bundle(output="target2")
        self.updater.build_done(bundle2, self.env)
        assert self.updater.needs_rebuild(self.bundle, self.env) == False

    def test_filters_changed(self):
        self.updater.build_done(self.bundle, self.env)
        self.bundle.filters += ('jsmin',)
        assert self.updater.needs_rebuild(self.bundle, self.env) == True

    def test_contents_changed(self):
        self.updater.build_done(self.bundle, self.env)
        self.bundle.contents += ('foo.css',)
        assert self.updater.needs_rebuild(self.bundle, self.env) == True

    def test_debug_changed(self):
        self.updater.build_done(self.bundle, self.env)
        self.bundle.debug = not self.bundle.debug
        assert self.updater.needs_rebuild(self.bundle, self.env) == True

    def test_depends_changed(self):
        # Changing the depends attribute of a bundle will NOT cause
        # a rebuild. This is a close call, and might just as well work
        # differently. I decided that the purity of the Bundle.__hash__
        # implementation in not including anything that isn't affecting
        # to the final output bytes was more important. If the user
        # is changing depends than after the next rebuild that change
        # will be effective anyway.
        self.updater.build_done(self.bundle, self.env)
        self.bundle.depends += ['foo']
        assert self.updater.needs_rebuild(self.bundle, self.env) == False


class TestTimestampUpdater(TempEnvironmentHelper):

    default_files = {'in': '', 'out': ''}

    def setup(self):
        TempEnvironmentHelper.setup(self)

        # Test the timestamp updater with cache disabled, so that the
        # BundleDefUpdater() base class won't interfere.
        self.m.cache = False
        self.m.updater = TimestampUpdater()

    def test_timestamp_behavior(self):
        bundle = self.mkbundle('in', output='out')

        # Set both times to the same timestamp
        now = self.setmtime('in', 'out')
        assert self.m.updater.needs_rebuild(bundle, self.m) == False

        # Make in file older than out file
        now = self.setmtime('in', mtime=now-100)
        now = self.setmtime('out', mtime=now)
        assert self.m.updater.needs_rebuild(bundle, self.m) == False

        # Make in file newer than out file
        now = self.setmtime('in', mtime=now)
        now = self.setmtime('out', mtime=now-100)
        assert self.m.updater.needs_rebuild(bundle, self.m) == True

    def test_source_file_deleted(self):
        """If a source file is deleted, rather than raising an error
        when failing to check it's timestamp, we ask for a rebuild.

        The reason is that when a wildcard is used to build the list of
        source files, this is the behavior we want: At the time of the
        update check, we are presumably using a cached version of the
        bundle contents. For the rebuild, the contents are refreshed.

        So if the file that is missing was included via a wildcard, the
        rebuild will go through, without the file. If a file is gone
        missing that he user specifically added to the bundle, then the
        build process is going to raise the error (this is tested
        separately).
        """
        self.create_files({'1.css': '', '2.css': ''})
        bundle = self.mkbundle('in', '*.css', output='out')

        # Set all mtimes to the same timestamp
        self.setmtime('in', 'out', '1.css', '2.css')
        assert self.m.updater.needs_rebuild(bundle, self.m) == False

        # Delete a wildcarded file
        os.unlink(self.path('1.css'))
        assert self.m.updater.needs_rebuild(bundle, self.m) == True

    def test_bundle_definition_change(self):
        """Test that the timestamp updater uses the base class
        functionality of determining a bundle definition change as
        well.
        """
        self.m.cache = MemoryCache(capacity=100)
        bundle = self.mkbundle('in', output='out')
        now = time.time()

        # Fake an initial build
        self.m.updater.build_done(bundle, self.m)

        # Make in file older than out file
        os.utime(self.path('in'), (now, now-100))
        os.utime(self.path('out'), (now, now))
        assert self.m.updater.needs_rebuild(bundle, self.m) == False

        # Change the bundle definition
        bundle.filters = 'jsmin'

        # Timestamp updater will says we need to rebuild.
        assert self.m.updater.needs_rebuild(bundle, self.m) == True
        self.m.updater.build_done(bundle, self.m)

    def test_depends(self):
        """Test the timestamp updater properly considers additional
        bundle dependencies.
        """
        self.create_files({'d.sass': '', 'd.other': ''})
        bundle = self.mkbundle('in', output='out', depends=('*.sass',))

        # First, ensure that the dependency definition is not
        # unglobbed until we actually need to do it.
        internal_attr = '_resolved_depends'
        assert not getattr(bundle, internal_attr, None)

        now = time.time()

        # Make all files older than the output
        now = self.setmtime('out')
        self.setmtime('in', 'd.sass', 'd.other', mtime=now-100)
        assert self.m.updater.needs_rebuild(bundle, self.m) == False

        # Touch the file that is supposed to be unrelated
        self.setmtime('d.other', mtime=now+100)
        assert self.m.updater.needs_rebuild(bundle, self.m) == False

        # Touch the dependency file - now a rebuild is required
        self.setmtime('d.sass', mtime=now+100)
        assert self.m.updater.needs_rebuild(bundle, self.m) == SKIP_CACHE

        # Finally, counter-check that our previous check for the
        # internal attribute was valid.
        assert hasattr(bundle, internal_attr)

    def test_depends_nested(self):
        """Test the dependencies of a nested bundle are checked too.
        """
        self.create_files({'dependency': ''})
        bundle = self.mkbundle('in', Bundle('in', depends='dependency'),
                               output='out', )
        now = self.setmtime('out')
        self.setmtime('in', mtime=now-100)
        self.setmtime('dependency', mtime=now+100)

        assert self.m.updater.needs_rebuild(bundle, self.m) == SKIP_CACHE

    def test_wildcard_dependency_deleted(self):
        """If a dependency is deleted, a rebuild is always
        required.

        [Regression] This used to raise an error.
        """
        self.create_files({'1.sass': '', '2.sass': ''})
        bundle = self.mkbundle('in', output='out', depends=('*.sass',))

        # Set mtimes so that no update is required
        self.setmtime('1.sass', '2.sass', 'in', 'out')
        assert self.m.updater.needs_rebuild(bundle, self.m) == False

        # Delete a dependency
        os.unlink(self.path('1.sass'))
        # Now we need to update
        assert self.m.updater.needs_rebuild(bundle, self.m) == SKIP_CACHE

    def test_static_dependency_missing(self):
        """If a statically referenced dependency does not exist,
        an error is raised.
        """
        bundle = self.mkbundle('in', output='out', depends=('file',))
        assert_raises(BundleError, self.m.updater.needs_rebuild, bundle, self.m)
