import os
from os import path
import time
import shutil
import tempfile
from webassets import Environment, Bundle


__all__ = ('BuildTestHelper', 'noop')


# Define a noop filter; occasionally in tests we need to define
# a filter to be able to test a certain piece of functionality,.
noop = lambda _in, out: out.write(_in.read())


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

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, type, value, traceback):
        self.teardown()

    def mkbundle(self, *a, **kw):
        b = Bundle(*a, **kw)
        b.env = self.m
        return b

    def create_files(self, files):
        """Helper that allows to quickly create a bunch of files in
        the media directory of the current test run.
        """
        for name, data in files.items():
            f = open(self.path(name), 'w')
            f.write(data)
            f.close()

    def create_directories(self, *dirs):
        """Helper to create directories within the media directory
        of the current test's environment.
        """
        for dir in dirs:
            os.makedirs(self.path(dir))

    def exists(self, name):
        """Ensure the given file exists within the current test run's
        media directory.
        """
        return path.exists(self.path(name))

    def get(self, name):
        """Return the given file's contents.
        """
        return open(self.path(name)).read()

    def path(self, name):
        """Return the given file's full path."""
        return path.join(self.m.directory, name)

    def setmtime(self, *files, **kwargs):
        """Set the mtime of the given files. Useful helper when
        needing to test things like the timestamp updater.

        Specify ``mtime`` as a keyword argument, or time.time()
        will automatically be used. Returns the mtime used.
        """
        mtime = kwargs.pop('mtime', time.time())
        assert not kwargs, "Unsupported kwargs: %s" %  ', '.join(kwargs.keys())
        for f in files:
            os.utime(self.path(f), (mtime, mtime))
        return mtime

    def p(self, *files):
        """Print the contents of the given files to stdout; useful
        for some quick debugging.
        """
        for f in files:
            print f
            print "-" * len(f)
            print self.get(f)
            print
