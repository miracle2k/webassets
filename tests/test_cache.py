from nose.tools import assert_equals
from django_assets import Bundle
from django_assets.conf import settings
from django_assets.cache import BaseCache
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

	settings.ASSETS_CACHE = self.cache = MyCache()
	settings.DEBUG = True

    def test_cache_disabled(self):
	bundle = Bundle('in1', 'in2', output='out', filters="jsmin")
	self.cache.enabled = False
	bundle.build()
	assert_equals(self.cache.getops, 3)
	assert_equals(self.cache.setops, 3)

    def test_cache_enabled(self):
	bundle = Bundle('in1', 'in2', output='out', filters="jsmin")
	self.cache.enabled = True
	bundle.build()
	assert_equals(self.cache.getops, 3)
	assert_equals(self.cache.setops, 0)