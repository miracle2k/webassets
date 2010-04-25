# Configure Django for our tests. This can't be within a ``setup_package``
# function, or it will most likely only be executed after the django-assets
# conf module is imported, which then initializes itself based on an
# empty Django settings object.
from django.conf import settings
settings.configure()


def setup_package():
    # Unless explicitely tested, we don't want to use the cache.
    from django_assets.conf import settings
    settings.ASSETS_CACHE = False