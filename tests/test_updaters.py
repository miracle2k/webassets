import os
from nose.tools import assert_raises
from webassets import Environment, Bundle
from webassets.exceptions import BundleError, BuildError
from webassets.updater import TimestampUpdater, BundleDefUpdater, SKIP_CACHE
from webassets.cache import MemoryCache
from webassets.version import VersionIndeterminableError
from .helpers import TempEnvironmentHelper


class TestBundleDefBaseUpdater(object):
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
        # differently. I decided that the purity of the Bundle.id
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
        self.env.cache = False
        self.env.updater = self.updater = TimestampUpdater()

    def test_timestamp_behavior(self):
        bundle = self.mkbundle('in', output='out')

        # Set both times to the same timestamp
        now = self.setmtime('in', 'out')
        assert self.updater.needs_rebuild(bundle, self.env) == False

        # Make in file older than out file
        os.utime(self.path('in'), (now, now-100))
        os.utime(self.path('out'), (now, now))
        assert self.updater.needs_rebuild(bundle, self.env) == False

        # Make in file newer than out file
        os.utime(self.path('in'), (now, now))
        os.utime(self.path('out'), (now, now-100))
        assert self.updater.needs_rebuild(bundle, self.env) == True

    def test_source_file_deleted(self):
        """If a source file is deleted, rather than raising an error
        when failing to check its timestamp, we ask for a rebuild.

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
        assert self.updater.needs_rebuild(bundle, self.env) == False

        # Delete a wildcarded file
        os.unlink(self.path('1.css'))
        assert self.updater.needs_rebuild(bundle, self.env) == True

    def test_bundle_definition_change(self):
        """Test that the timestamp updater uses the base class
        functionality of determining a bundle definition change as
        well.
        """
        self.env.cache = MemoryCache(capacity=100)
        bundle = self.mkbundle('in', output='out')

        # Fake an initial build
        self.updater.build_done(bundle, self.env)

        # Make in file older than out file
        now = self.setmtime('out')
        self.setmtime('in', mtime=now-100)
        assert self.updater.needs_rebuild(bundle, self.env) == False

        # Change the bundle definition
        bundle.filters = 'jsmin'

        # Timestamp updater will says we need to rebuild.
        assert self.updater.needs_rebuild(bundle, self.env) == True
        self.updater.build_done(bundle, self.env)

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

        # Make all files older than the output
        now = self.setmtime('out')
        self.setmtime('in', 'd.sass', 'd.other', mtime=now-100)
        assert self.updater.needs_rebuild(bundle, self.env) == False

        # Touch the file that is supposed to be unrelated
        now = self.setmtime('d.other', mtime=now+100)
        assert self.updater.needs_rebuild(bundle, self.env) == False

        # Touch the dependency file - now a rebuild is required
        now = self.setmtime('d.sass', mtime=now+100)
        assert self.updater.needs_rebuild(bundle, self.env) == SKIP_CACHE

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

        assert self.updater.needs_rebuild(bundle, self.env) == SKIP_CACHE

    def test_wildcard_dependency_deleted(self):
        """If a dependency is deleted, a rebuild is always
        required.

        [Regression] This used to raise an error.
        """
        self.create_files({'1.sass': '', '2.sass': ''})
        bundle = self.mkbundle('in', output='out', depends=('*.sass',))

        # Set mtimes so that no update is required
        self.setmtime('1.sass', '2.sass', 'in', 'out')
        assert self.updater.needs_rebuild(bundle, self.env) == False

        # Delete a dependency
        os.unlink(self.path('1.sass'))
        # Now we need to update
        assert self.updater.needs_rebuild(bundle, self.env) == SKIP_CACHE

    def test_static_dependency_missing(self):
        """If a statically referenced dependency does not exist,
        an error is raised.
        """
        bundle = self.mkbundle('in', output='out', depends=('file',))
        assert_raises(BundleError, self.updater.needs_rebuild, bundle, self.env)

    def test_changed_file_after_nested_bundle(self):
        """[Regression] Regression-test for a particular bug where the
        changed file was listed after a nested bundle and the change
        was not picked up.
        """
        self.env.updater = 'timestamp'
        self.env.cache = False
        self.create_files(['nested', 'main', 'out'])
        b = self.mkbundle(Bundle('nested'), 'main', output='out')

        # Set timestamps
        now = self.setmtime('out')
        self.setmtime('nested', mtime=now-100)  # unchanged
        self.setmtime('main', mtime=now+100)  # changed

        # At this point, a rebuild is required.
        assert self.env.updater.needs_rebuild(b, self.env) == True

    def test_placeholder_output(self):
        """Test behaviour if the output contains a placeholder."""
        from .test_bundle_various import DummyVersion
        self.env.versions = DummyVersion('init')
        self.env.manifest = None
        b = self.mkbundle('in', output='out-%(version)s')

        # True, because the output file does not yet exist
        assert self.env.updater.needs_rebuild(b, self.env) == True

        # After a build, no update required anymore
        b.build(force=True)
        assert self.env.updater.needs_rebuild(b, self.env) == False

        # If we change the date, update is required again
        now = self.setmtime('out-init')
        self.setmtime('in', mtime=now+100)
        assert self.env.updater.needs_rebuild(b, self.env) == True

        # If we change the version, a rebuild will be required
        # because the output file once again no longer exists
        b.build(force=True)
        self.env.versions.version = 'something-else'
        assert self.env.updater.needs_rebuild(b, self.env) == True

    def test_placeholder_with_limited_versioner(self):
        """If output has a placeholder, and the versioner is unable to
        return a version in such a case, then the timestamp updater will
        explicitly check if a manifest is enabled.

        If is is, the version from there is enough to reasonable work
        an update check.

        If it isn't, then the updater refuses to work, not being able to
        do its job.
        """
        from .test_bundle_various import DummyVersion, DummyManifest

        # Placeholder output, and versioner will not help
        self.env.versions = DummyVersion(None)
        b = self.mkbundle('in', output='out-%(version)s')

        # Confirm DummyVersion works as we expect it to.
        assert_raises(VersionIndeterminableError,
            self.env.versions.determine_version, b, self.env)

        # Without a manifest, an error is raised. With no version being
        # available, we cannot check at all whether an update is required.
        # We would have to blindly return YES, PROCEED WITH BUILD every
        # time, thus not doing our job.
        self.env.manifest = None
        assert_raises(BuildError, self.env.updater.needs_rebuild, b, self.env)

        # As soon as a manifest is set, the updater will start to work,
        # even if the manifest does not actually have a version. This is
        # of course because this will be the case for the first build.
        # After the next build, the updater can assume (if the manifest
        # works correctly), that a version will be available.
        self.env.manifest = DummyManifest(None)
        assert self.env.updater.needs_rebuild(b, self.env) == True

        # The same is true if the manifest returns an actual version
        self.env.manifest.version = 'v1'
        assert self.env.updater.needs_rebuild(b, self.env) == True

        # If the file behind that version actually exists, it will be used.
        self.create_files(['out-v1'])
        now = self.setmtime('out-v1')
        self.setmtime('in', mtime=now-100)
        assert self.env.updater.needs_rebuild(b, self.env) == False
