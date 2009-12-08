import default as default_settings
from django.conf import settings as django_settings

class WrappedSettings(object):
    """Wraps around the Django settings, falling back to our own
    default settings module.
    """

    def __init__(self, *setting_objs):
        self.setting_objs = setting_objs

    def __getattr__(self, name):
        for settings in self.setting_objs:
            if hasattr(settings, name):
                return getattr(settings, name)
        raise AttributeError()

settings = WrappedSettings(django_settings, default_settings)