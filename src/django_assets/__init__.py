# Make a couple frequently used things available right here.
from webassets.bundle import Bundle
from django_assets.env import register


__all__ = ('Bundle', 'register')


from django_assets import filter
