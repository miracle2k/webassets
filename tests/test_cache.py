from nose.tools import assert_equals
from webassets import Bundle, Environment
from webassets.cache import BaseCache
from helpers import BuildTestHelper


class TestCache(BuildTestHelper):

    def setup(self):
        BuildTestHelper.setup(self)

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

        self.m.cache = self.cache = MyCache()
        self.m.debug = True

    def test_cache_disabled(self):
        bundle = self.mkbundle('in1', 'in2', output='out', filters="jsmin")
        self.cache.enabled = False
        bundle.build()
        assert_equals(self.cache.getops, 3)
        assert_equals(self.cache.setops, 3)

    def test_cache_enabled(self):
        bundle = self.mkbundle('in1', 'in2', output='out', filters="jsmin")
        self.cache.enabled = True
        bundle.build()
        assert_equals(self.cache.getops, 3)
        assert_equals(self.cache.setops, 0)