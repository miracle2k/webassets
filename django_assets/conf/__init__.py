from itertools import chain
import default as default_settings
from django.conf import settings as django_settings


class WrappedSettings(object):
    """Wraps around the Django settings, falling back to our own
    default settings module.
    """
    __slots__ = ('_live_settings', '_fallbacks',)

    def __init__(self, live_settings, *fallbacks):
        self._live_settings = live_settings
        self._fallbacks = fallbacks

    def __getattr__(self, name):
        for settings in chain([self._live_settings], self._fallbacks):
            if hasattr(settings, name):
                return getattr(settings, name)
        raise AttributeError()

    def __setattr__(self, name, value):
        if name in self.__slots__:
            object.__setattr__(self, name, value)
        else:
            setattr(self._live_settings, name, value)


settings = WrappedSettings(django_settings, default_settings)