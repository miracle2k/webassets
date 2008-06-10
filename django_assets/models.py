from django_assets.conf import settings

if settings.TRACK_ASSETS == 'model':
    from django.db import models

    class Asset(models.Model):
        """
        output = primary_key
        sources = textfield
        last_touched
        last_updated
        hash
        """

        class Meta:
            pass