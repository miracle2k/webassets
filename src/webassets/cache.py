"""The cache is used to speed up asset building. Filter operations every
step of the way can be cached, so that individual parts of a build that
haven't changed can be reused.
"""

import os
from os import path
from filter import Filter


__all__ = ('FilesystemCache', 'get_cache',)


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
        filename = path.join(self.directory, hash(key))
        if not path.exists(filename):
            return False
        f = open(filename, 'rb')
        try:
            return f.read()
        finally:
            f.close()

    def set(self, key, data):
        filename = path.join(self.directory, hash(key))
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