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

    # We can also access values that are not represented by a original
    # Django setting. Specifically, we are able to read those values
    # and get the webassets-default without having to explicitly
    # initialize the corresponding Django setting.
    assert django_env.debug == False
    assert not hasattr(settings, 'ASSETS_DEBUG')
    django_env.debug = True
    assert settings.ASSETS_DEBUG == True


def test_config():
    """The Environment config storage is also backed by the Django
    settings object.
    """
    settings.FOO = 42
    django_env.get_config('FOO') == 42
