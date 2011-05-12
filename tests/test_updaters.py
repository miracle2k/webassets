import os, time
from webassets import Environment, Bundle
from webassets.updater import TimestampUpdater, BundleDefUpdater
from webassets.cache import MemoryCache
from helpers import BuildTestHelper


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


class TestTimestampUpdater(BuildTestHelper):

    default_files = {'in': '', 'out': ''}

    def setup(self):
        BuildTestHelper.setup(self)

        # Test the timestamp updater with cache disabled, so that the
        # BundleDefUpdater() base class won't interfere.
        self.m.cache = False
        self.m.updater = "timestamp"

    def test_default(self):
        bundle = self.mkbundle('in', output='out')
        now = time.time()

        # Set both times to the same timestamp
        os.utime(self.path('in'), (now, now))
        os.utime(self.path('out'), (now, now))
        assert self.m.updater.needs_rebuild(bundle, self.m) == False

        # Make in file older than out file
        os.utime(self.path('in'), (now, now-100))
        os.utime(self.path('out'), (now, now))
        assert self.m.updater.needs_rebuild(bundle, self.m) == False

        # Make in file newer than out file
        os.utime(self.path('in'), (now, now))
        os.utime(self.path('out'), (now, now-100))
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


