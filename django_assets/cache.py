"""The cache is used to speed up asset building. Filter operations every
step of the way can be cached, so that individual parts of a build that
haven't changed can be reused.
"""

import os
from os import path
from django_assets.conf import settings
from django_assets.filter import Filter
from django.utils.hashcompat import md5_constructor


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


def get_cache():
    """Get a cache object for the currently configured environment.
    """
    if not settings.DEBUG or not settings.ASSETS_CACHE:
        return DummyCache()

    if isinstance(settings.ASSETS_CACHE, BaseCache):
        return settings.ASSETS_CACHE
    elif isinstance(settings.ASSETS_CACHE, type) and issubclass(settings.ASSETS_CACHE, BaseCache):
        return settings.ASSETS_CACHE()

    if settings.ASSETS_CACHE is True:
        directory = path.join(settings.MEDIA_ROOT, '.cache')
        # Auto-create the default directory
        if not path.exists(directory):
            os.makedirs(directory)
    else:
        directory = settings.ASSETS_CACHE
    return FilesystemCache(directory)