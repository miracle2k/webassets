import os
from os import path
import shutil
import tempfile
from webassets import Environment, Bundle


__all__ = ('BuildTestHelper',)


class BuildTestHelper:
    """Provides some basic helpers for tests that want to simulate
    building bundles.
    """

    default_files = {'in1': 'A', 'in2': 'B', 'in3': 'C', 'in4': 'D'}

    def setup(self):
        self.dir_created = tempfile.mkdtemp()
        self.m = Environment(self.dir_created, '')
        # Unless we explicitly test it, we don't want to use the cache
        # during testing.
        self.m.cache = False

        # Some generic files to be used by simple tests
        self.create_files(self.default_files)

    def teardown(self):
        # Make sure to use a separate attribute for security. We don't
        # want to delete the actual media directory if a child class
        # to call super() in setup().
        shutil.rmtree(self.dir_created)

    def mkbundle(self, *a, **kw):
        b = Bundle(*a, **kw)
        b.env = self.m
        return b

    def create_files(self, files):
        """Helper that allows to quickly create a bunch of files in
        the media directory of the current test run.
        """
        for name, data in files.items():
            f = open(path.join(self.m.directory, name), 'w')
            f.write(data)
            f.close()

    def create_directories(self, *dirs):
        """Helper to create directories within the media directory
        of the current test's environment.
        """
        for dir in dirs:
            os.makedirs(path.join(self.m.directory, dir))

    def exists(self, name):
        """Ensure the given file exists within the current test run's
        media directory.
        """
        return path.exists(path.join(self.m.directory, name))

    def get(self, name):
        """Return the given file's contents.
        """
        return open(path.join(self.m.directory, name)).read()