from django.conf import settings
from django.contrib import staticfiles
from django.contrib.staticfiles.utils import matches_patterns
from django.core.files.storage import FileSystemStorage
from django_assets.env import get_env


class AssetsFileStorage(FileSystemStorage):
    def __init__(self, location=None, base_url=None, *args, **kwargs):
        super(AssetsFileStorage, self).__init__(
            location or get_env().directory,
            base_url or get_env().url,
            *args, **kwargs)


class AssetsFinder(staticfiles.finders.BaseStorageFinder):
    """A staticfiles finder that will serve from ASSETS_ROOT (which
    defaults to STATIC_ROOT).

    This is required when using the django.contrib.staticfiles app
    in development, because the Django devserver will not serve files
    from STATIC_ROOT (or ASSETS_ROOT) by default - which is were the
    merged assets are written.
    """
    # NOTE: We don't have to worry about this "finding" all the
    # output files of "collectstatic" during a "collectstatic" run.
    # staticfiles is smart enough to recognize that the files have
    # not changed (being the same files), and doesn't overwrite them.
    storage = AssetsFileStorage

    def list(self, ignore_patterns):
        env = get_env()
        if env.directory == getattr(settings, 'STATIC_ROOT'):
            for bundle in env:
                if not matches_patterns(bundle.output, ignore_patterns) and \
                 self.storage.exists(bundle.output):
                    yield bundle.output, self.storage
        else:
            # We can't just return the list since return can't coexist
            # with above yield
            for output in super(AssetsFinder, self).list(ignore_patterns):
                yield output
