from django.conf import settings
from django_assets import register
from django_assets.manager import manager as django_manager


def setup_module():
    from django.conf import settings
    settings.configure()


def test_options():
    """Various AssetManager options are backed by the Django settings
    object.
    """
    settings.MEDIA_ROOT = 'FOO'
    assert django_manager.directory == 'FOO'

    django_manager.directory = 'BAR'
    assert settings.MEDIA_ROOT == 'BAR'

    # TODO
    print django_manager.expire


def test_config():
    """The AssetManager config storage is also backed by the Django
    settings object.
    """
    settings.FOO = 42
    django_manager.get_config('FOO') == 42
