from os import path
import shutil
import tempfile

from django_assets.conf import settings


__all__ = ('BuildTestHelper',)


# If you change a setting during one of these tests, make sure it is
# listed here, so you're change will be reverted on test teardown.
RESETTABLE_SETTINGS = ('ASSETS_AUTO_CREATE', 'ASSETS_UPDATER', 'DEBUG',
                       'ASSETS_DEBUG', 'ASSETS_EXPIRE', 'MEDIA_URL',
                       'MEDIA_ROOT',)


class BuildTestHelper:
    """Provides some basic helpers for tests that want to simulate
    building bundles.
    """

    default_files = {'in1': 'A', 'in2': 'B', 'in3': 'C', 'in4': 'D'}

    def setup(self):
        self.old_settings = {}
        for name in RESETTABLE_SETTINGS:
            self.old_settings[name] = getattr(settings, name)

        settings.MEDIA_ROOT = self.dir_created = tempfile.mkdtemp()

        # Some generic files to be used by simple tests
        self.create_files(self.default_files)

    def teardown(self):
        shutil.rmtree(self.dir_created)

        # Reset settings that we may have changed.
        for key, value in self.old_settings.items():
            setattr(settings, key, value)

    def create_files(self, files):
        """Helper that allows to quickly create a bunch of files in
        the media directory of the current test run.
        """
        for name, data in files.items():
            f = open(path.join(settings.MEDIA_ROOT, name), 'w')
            f.write(data)
            f.close()

    def exists(self, name):
        """Ensure the given file exists within the current test run's
        media directory.
        """
        return path.exists(path.join(settings.MEDIA_ROOT, name))

    def get(self, name):
        """Return the given file's contents.
        """
        return open(path.join(settings.MEDIA_ROOT, name)).read()