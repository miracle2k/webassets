import default as default_settings
from django.conf import settings as django_settings

from django.conf import UserSettingsHolder
settings = UserSettingsHolder(default_settings)
for name in dir(django_settings):
    if name == name.upper():
        value = getattr(django_settings, name)
        setattr(settings, name, value)