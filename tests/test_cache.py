import tempfile, shutil
from nose.tools import assert_equals
from webassets.filter import Filter
from webassets.cache import BaseCache, FilesystemCache, MemoryCache
from helpers import TempEnvironmentHelper


class TestCaches:
    """Test the individual cache classes directly.
    """

    def test_filesystem_cache(self):
        cachedir = tempfile.mkdtemp()
        try:
            c = FilesystemCache(cachedir)
            assert c.get('non-existant') == None
            c.set('foo', 'bar')
            assert c.get('foo') == 'bar'
        finally:
            shutil.rmtree(cachedir)

    def test_memory_cache(self):
        c = MemoryCache(capacity=2)
        assert c.get('non-existant') == None
        c.set('foo', 'bar')
        assert c.get('foo') == 'bar'
        # Since we have capacity=2, adding two more keys will
        # remove the first one.
        c.set('key2', 'value2')
        c.set('key3', 'value3')
        assert c.get('foo') == None


class TestCacheIsUsed(TempEnvironmentHelper):
    """Ensure the cache is used during the build process.
    """

    def setup(self):
        TempEnvironmentHelper.setup(self)

        class MyCache(BaseCache):
            def __init__(self):
                self.enabled = False
                self.reset()
            def get(self, key):
                self.getops += 1
                if self.enabled:
                    return 'foo'
                return False
            def set(self, key, data):
                self.setops += 1
            def reset(self):
                self.getops = 0
                self.setops = 0

        class CompleteFilter(Filter):
            # Support all possible filter operations
            def input(self, _in, out, **kw):
                pass
            output = first = input
        self.filter = CompleteFilter

        self.m.cache = self.cache = MyCache()
        # Note that updater will use the cache also
        self.m.updater = 'timestamp'

    def test_cache_disabled(self):
        bundle = self.mkbundle('in1', 'in2', output='out', filters=self.filter)
        self.cache.enabled = False
        bundle.build()
        assert_equals(self.cache.getops, 5)  # 2x first, 2x input, 1x output
        assert_equals(self.cache.setops, 6)  # like getops + 1x bdef

    def test_cache_enabled(self):
        bundle = self.mkbundle('in1', 'in2', output='out', filters=self.filter)
        self.cache.enabled = True
        bundle.build()
        assert_equals(self.cache.getops, 5)  # 2x first, 2x input, 1x output
        assert_equals(self.cache.setops, 1)  # one hit by (bdef)

    def test_filesystem_cache(self):
        """Regresssion test for two bugs:
        One where the FilesystemCache class was called with an
        unhashable key (which is not allowed), the second where the
        updater tried to cache a non-string value.

        Both in the process of a standard build.
        """
        bundle = self.mkbundle('in1', 'in2', output='out', filters="jsmin")
        self.m.cache = True   # use the filesystem cache
        self.m.updater = 'timestamp'
        bundle.build(force=True)

