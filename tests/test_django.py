from django.conf import settings
from django_assets import register
from django_assets.env import env as django_env


def setup_module():
    from django.conf import settings
    settings.configure()


def test_options():
    """Various Environment options are backed by the Django settings
    object.
    """
    settings.MEDIA_ROOT = 'FOO'
    assert django_env.directory == 'FOO'

    django_env.directory = 'BAR'
    assert settings.MEDIA_ROOT == 'BAR'

    # TODO
    print django_env.expire


def test_config():
    """The Environment config storage is also backed by the Django
    settings object.
    """
    settings.FOO = 42
    django_env.get_config('FOO') == 42
