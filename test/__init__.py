# Configure Django for our tests. This can't be within a ``setup_package``
# function, or it will most likely only be executed after the django-assets
# conf module is imported, which then initializes itself based on an
# empty Django settings object.
from django.conf import settings
settings.configure()