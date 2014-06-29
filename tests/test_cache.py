from __future__ import with_statement

import random
import pytest
from nose.tools import assert_equal
from webassets.filter import Filter
from webassets.cache import BaseCache, FilesystemCache, MemoryCache
from webassets.updater import TimestampUpdater
from webassets.merge import MemoryHunk
from .helpers import TempEnvironmentHelper, TempDirHelper


def pytest_generate_tests(metafunc):
    if 'c' in metafunc.fixturenames:
        metafunc.parametrize("c", [FilesystemCache, MemoryCache], indirect=True)


@pytest.fixture()
def c(request):
    helper = TempDirHelper()
    helper.__enter__()

    if request.param == FilesystemCache:
        c = FilesystemCache(helper.tempdir)
    elif request.param == MemoryCache:
        c = MemoryCache(capacity=10000)
    else:
        raise ValueError(request.param)

    def end():
        helper.__exit__(None, None, None)
    request.addfinalizer(end)
    return c


class TestCacheClasses(object):
    """Test the individual cache classes directly.
    """

    def test_simple(self, c):
        # Simple get,set
        assert c.get('non-existant') is None
        c.set('foo', 'bar')
        assert c.get('foo') == 'bar'

    def test_hunks(self, c):
        """Test hunks as keys."""
        key = (MemoryHunk('bla'), 42)
        assert c.get(key) is None
        c.set(key, 'foo')
        assert c.get(key) == 'foo'
        assert c.get((MemoryHunk('bla'), 42)) == 'foo'

    def test_filters(self, c):
        """Test filters as keys."""
        class MyFilter(Filter):
            pass
        key = (MyFilter(), 42)
        assert c.get(key) is None
        c.set(key, 'foo')
        assert c.get(key) == 'foo'
        assert c.get((MyFilter(), 42)) == 'foo'

    def _test_dicts(self, c):
        """Attention needs to be paid here due to undefined order."""
        values = ['%s'% i for i in range(0, 10)]
        key = dict([(v, v) for v in values])
        assert c.get(key) is None
        c.set(key, 'foo')
        assert c.get(key) == 'foo'

        # Shuffling really doesn't seem to have any effect on the key order.
        # This test is pretty meaningless then.
        random.shuffle(values)
        assert c.get(dict([(v, v) for v in values])) == 'foo'

    def test_memory_cache_capacity(self):
        c = MemoryCache(capacity=2)
        c.set('foo', 'bar')
        assert c.get('foo') == 'bar'
        # Since we have capacity=2, adding two more keys will
        # remove the first one.
        c.set('key2', 'value2')
        c.set('key3', 'value3')
        assert c.get('foo') is None


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
                    return u'foo'
                return False
            def set(self, key, data):
                self.setops += 1
            def reset(self):
                self.getops = 0
                self.setops = 0

        class CompleteFilter(Filter):
            # Support all possible filter operations
            def input(self, *a, **kw):
                pass
            output = open = concat = input
        self.filter = CompleteFilter

        self.env.cache = self.cache = MyCache()
        self.env.manifest = None
        # Note that updater will use the cache also
        self.env.updater = TimestampUpdater()

    def test_cache_disabled(self):
        bundle = self.mkbundle('in1', 'in2', output='out', filters=self.filter)
        self.cache.enabled = False
        bundle.build()
        assert_equal(self.cache.getops, 6)  # 2x first, 2x input, 1x output, 1x cache
        assert_equal(self.cache.setops, 7)  # like getops + 1x bdef

    def test_cache_enabled(self):
        bundle = self.mkbundle('in1', 'in2', output='out', filters=self.filter)
        self.cache.enabled = True
        bundle.build()
        assert_equal(self.cache.getops, 6)  # # 2x first, 2x input, 1x output, 1x cache
        assert_equal(self.cache.setops, 1)  # one hit by (bdef)

    def test_filesystem_cache(self):
        """Regresssion test for two bugs:
        One where the FilesystemCache class was called with an
        unhashable key (which is not allowed), the second where the
        updater tried to cache a non-string value.

        Both in the process of a standard build.
        """
        bundle = self.mkbundle('in1', 'in2', output='out', filters="rjsmin")
        self.env.cache = True   # use the filesystem cache
        self.env.updater = TimestampUpdater()
        bundle.build(force=True)


class TestSpecialCases(TempEnvironmentHelper):
    """Test cachy-things that don't have a place elsewhere.

    I'm not sure if this should be here or in test_bundles. test_bundles
    is getting large though.
    """

    def test_open_filter_and_cache(self):
        """[Regression] The open() filter method used to only use the filename
        as a cache key, leading to any changes being ignored.
        """
        self.env.cache = True   # use the filesystem cache
        class OpenFilter(Filter):
            content = 'foo'
            def open(self, out, source_path, **kw):
                with open(source_path) as f:
                    out.write(f.read())
        open_filter = OpenFilter()

        self.create_files({'in1': 'foo'})
        bundle = self.mkbundle('in1', output='out', filters=open_filter)
        bundle.build(force=True)

        self.create_files({'in1': 'bar'})
        bundle.build(force=True)
        assert self.get('out') == 'bar'
