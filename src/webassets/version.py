"""This module defines "version" classes that can be assigned to the
``Environment.versioner`` attribute.

A version class, given a bundle, can determine the "version" of this
bundle. This version can then be used in the output filename of the
bundle, or appended to the url as a query string, in order to expire
cached assets.

A version could be a timestamp, a content hash, or a git revision.

As a user, all you need to care about, in most cases, is whether you
want to set the ``Environment.versioner`` attribute to ``hash``,
or leave it at the default, ``timestamp``.
"""

from updater import TimestampUpdater


__all__ = ('get_versioner', 'BaseVersion', 'TimestampVersion', 'HashVersion')


class BaseVersion(object):
    
    class __metaclass__(type):
        VERSIONERS = {}

        def __new__(cls, name, bases, attrs):
            new_klass = type.__new__(cls, name, bases, attrs)
            if hasattr(new_klass, 'id'):
                cls.VERSIONERS[new_klass.id] = new_klass
            return new_klass

        def get_versioner(cls, thing):
            if hasattr(thing, 'get_version_for'):
                if isinstance(thing, type):
                    return thing()
                return thing
            if not thing:
                return None
            try:
                return cls.VERSIONERS[thing]()
            except KeyError:
                raise ValueError('Versioner "%s" is not valid.' % thing)

    default_updater = TimestampUpdater

    def __eq__(self, other):
        """Return equality with the config values
        that instantiate this instance.
        """
        return (hasattr(self, 'id') and self.id == other) or \
               id(self) == id(other)    

    def get_version_for(self, bundle, env):
        """Return a string that represents the current version
        of the given bundle.
        """
        raise NotImplementedError()

    def _get_updater(self):
        if not hasattr(self, '_updater'):
            self._updater = self.default_updater()
        return self._updater
    def _set_updater(self, value):
        self._updater = value
    updater = property(_get_updater, _set_updater, doc="""
    Updater to use to determine whether a rebuild is required.

    This is an attribute of the Version class, because whether or
    not a rebuild is required is essentially a function of the
    "version" concept.
    """)


get_versioner = BaseVersion.get_versioner


class TimestampVersion(BaseVersion):

    id = 'timestamp'

    def get_version_for(self, bundle, env):
        raise NotImplementedError()


class HashVersion(BaseVersion):

    id = 'hash'

    def get_version_for(self, bundle, env):
        raise NotImplementedError()
