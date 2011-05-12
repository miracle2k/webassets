"""Caches are used for multiple things:

    - To speed up asset building. Filter operations every step
      of the way can be cached, so that individual parts of a
      build that haven't changed can be reused.

    - Bundle definitions are cached when a bundle is built so we
      can determine whether they have changed and whether a rebuild
      is required.

This data is not all stored in the same cache necessarily. The
classes in this module provide the "environment.cache" object, but
also serve in other places.
"""

import os
from os import path

from filter import Filter


__all__ = ('FilesystemCache', 'MemoryCache', 'get_cache',)


class BaseCache(object):
    """Abstract base class.

    The cache key must be something that is supported by the
    Python hash() function.

    Since the cache is used for multiple purposes, all
    webassets-internal code should always tag it's keys with
    an id, like so:

        key = ("tag", actual_key)
    """

    def get(self, key):
        """Should return the cache contents, or False."""
        raise NotImplementedError()

    def set(self, key):
        raise NotImplementedError()


class MemoryCache(BaseCache):
    """Caches stuff in the process memory.

    WARNING: Do NOT use this in a production environment, where you
    are likely going to have multiple processes serving the same app!
    """

    def __init__(self, capacity):
        self.capacity = capacity
        self.keys = []
        self.cache = {}

    def __eq__(self, other):
        """Return equality with the config values
        that instantiate this instance.
        """
        return False == other or \
               None == other or \
               id(self) == id(other)

    def get(self, key):
        return self.cache.get(key, None)

    def set(self, key, value):
        self.cache[key] = value
        try:
            self.keys.remove(key)
        except ValueError:
            pass
        self.keys.append(key)

        # limit cache to the given capacity
        to_delete = self.keys[0:max(0, len(self.keys)-self.capacity)]
        self.keys = self.keys[len(to_delete):]
        for item in to_delete:
            del self.cache[key]


class MemoryCache(BaseCache):
    """Caches stuff in the process memory.

    WARNING: Do NOT use this in a production environment, where you
    are likely going to have multiple processes serving the same app!
    """

    def __init__(self, capacity):
        self.capacity = capacity
        self.keys = []
        self.cache = {}

    def __eq__(self, other):
        """Return equality with the config values
        that instantiate this instance.
        """
        return False == other or \
               None == other or \
               id(self) == id(other)

    def get(self, key):
        return self.cache.get(key, None)

    def set(self, key, value):
        self.cache[key] = value
        try:
            self.keys.remove(key)
        except ValueError:
            pass
        self.keys.append(key)

        # limit cache to the given capacity
        to_delete = self.keys[0:max(0, len(self.keys)-self.capacity)]
        self.keys = self.keys[len(to_delete):]
        for item in to_delete:
            del self.cache[item]


class FilesystemCache(BaseCache):
    """Uses a temporary directory on the disk.
    """

    def __init__(self, directory):
        self.directory = directory

    def __eq__(self, other):
        """Return equality with the config values
        that instantiate this instance.
        """
        return True == other or \
               self.directory == other or \
               id(self) == id(other)

    def get(self, key):
        filename = path.join(self.directory, '%s' % hash(key))
        if not path.exists(filename):
            return None
        f = open(filename, 'rb')
        try:
            return f.read()
        finally:
            f.close()

    def set(self, key, data):
        filename = path.join(self.directory, '%s' % hash(key))
        f = open(filename, 'wb')
        try:
            f.write(data)
        finally:
            f.close()


def get_cache(option, env):
    """Return a cache instance based on ``option``.
    """
    if not option:
        return None

    if isinstance(option, BaseCache):
        return option
    elif isinstance(option, type) and issubclass(option, BaseCache):
        return option()

    if option is True:
        directory = path.join(env.directory, '.webassets-cache')
        # Auto-create the default directory
        if not path.exists(directory):
            os.makedirs(directory)
    else:
        directory = option
    return FilesystemCache(directory)
