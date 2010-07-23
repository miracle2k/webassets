"""The cache is used to speed up asset building. Filter operations every
step of the way can be cached, so that individual parts of a build that
haven't changed can be reused.
"""

import os
from os import path
from filter import Filter

import sys
if sys.version_info >= (2, 5):
    import hashlib
    md5_constructor = hashlib.md5
else:
    import md5
    md5_constructor = md5.new


__all__ = ('FilesystemCache', 'get_cache', 'make_key',)


def make_key(*stuff):
    """Create a cache key by hasing the given data.

    This knows about certain data types that are relevant for us,
    for example filters.
    """
    # MD5 is faster than sha, and we don't care so much about collisions
    md5 = md5_constructor()
    def feed(data):
        for d in data:
            if isinstance(d, list):
                feed(d)
            elif isinstance(d, Filter):
                md5.update("%d" % d.id())
            else:
                md5.update(str(d))
    feed(stuff)
    return md5.hexdigest()


class BaseCache(object):
    """Abstract base class.
    """

    def get(self, key):
        """Should return the cache contents, or False."""
        raise NotImplementedError()

    def set(self, key):
        raise NotImplementedError()


class FilesystemCache(BaseCache):
    """Uses a temporary directory on the disk.
    """

    def __init__(self, directory):
        self.directory = directory

    def get(self, key):
        filename = path.join(self.directory, key)
        if not path.exists(filename):
            return False
        f = open(filename, 'rb')
        try:
            return f.read()
        finally:
            f.close()

    def set(self, key, data):
        filename = path.join(self.directory, key)
        f = open(filename, 'wb')
        try:
            f.write(data)
        finally:
            f.close()


class DummyCache(BaseCache):
    """Cache that doesn't actually cache things."""

    def get(self, key):
        return False

    def set(self, key, data):
        pass


def get_cache(env):
    """Get a cache object for the given environment.
    """
    if not env.debug or not env.cache:
        return None

    if isinstance(env.cache, BaseCache):
        return env.cache
    elif isinstance(env.cache, type) and issubclass(env.cache, BaseCache):
        return env.cache()

    if env.cache is True:
        directory = path.join(env.directory, '.cache')
        # Auto-create the default directory
        if not path.exists(directory):
            os.makedirs(directory)
    else:
        directory = env.cache
    return FilesystemCache(directory)