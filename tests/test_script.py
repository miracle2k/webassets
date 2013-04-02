"""TODO: More commands need testing.

TODO: Looking at how we need to make the MockBundle write to``output``,
I wonder whether I shouldn't just do full-stack tests here instead of mocking.
"""

from __future__ import with_statement

import logging
from threading import Thread, Event
from nose.tools import assert_raises
from nose import SkipTest
import time

try:
    import argparse
except ImportError:
    raise SkipTest()

from webassets import Bundle
from webassets.exceptions import BuildError
from webassets.script import (
    main, CommandLineEnvironment, CommandError, GenericArgparseImplementation)
from webassets.test import TempEnvironmentHelper
from webassets.utils import working_directory


def test_script():
    """Test simply that the main script can be invoked."""
    main([])


class MockBundle(Bundle):
    build_called = False
    on_build = None
    def _build(self, *a, **kw):
        self.build_called = (True, a, kw)
        self.on_build(*a, **kw) if self.on_build else None


class TestCLI(TempEnvironmentHelper):

    def setup(self):
        super(TestCLI, self).setup()
        self.assets_env = self.env
        self.cmd_env = CommandLineEnvironment(self.assets_env, logging)


class TestBuildCommand(TestCLI):

    def test_generic(self):
        """Test the build command."""
        a = MockBundle(output='a')
        self.assets_env.add(a)
        self.cmd_env.build()
        assert a.build_called

    def test_build_container_bundles(self):
        """Test the build command can deal with container bundles.
        """
        a = MockBundle(output='a')
        b1 = MockBundle(output='b1')
        b2 = MockBundle(output='b2')
        b = MockBundle(b1, b2)
        self.assets_env.add(a, b)

        self.cmd_env.build()

        assert a.build_called
        assert not b.build_called
        assert b1.build_called
        assert b2.build_called

    def test_specific_bundles(self):
        """Test building specific bundles."""
        a = MockBundle(output='a')
        b = MockBundle(output='b')
        self.assets_env.register('a', a)
        self.assets_env.register('b', b)
        self.cmd_env.build(bundles=['a'])
        assert a.build_called
        assert not b.build_called

    def test_custom_filename(self):
        """Test specifying a custom output filename.
        """
        a = MockBundle(output='a')
        a.on_build = lambda *a, **kw: kw.get('output').write(u'FOO')
        b = MockBundle(output='b')
        self.assets_env.register('a', a)
        self.assets_env.register('b', b)
        self.cmd_env.build(output=[('a', self.path('custom'))])
        assert a.build_called
        assert not b.build_called
        assert self.get('custom') == 'FOO'

        # Building to a non-existing path would fail, directories
        # are not auto-created here.
        assert_raises(IOError, self.cmd_env.build,
            output=[('a', self.path('new/custom'))])

    def test_custom_directory(self):
        """Test specifying a custom output directory.
        """
        a = MockBundle(output='common/branch1/a')
        b = MockBundle(output='common/branch2/b')
        a.on_build = lambda *a, **kw: kw.get('output').write(u'FOO')
        b.on_build = a.on_build
        self.assets_env.register('a', a)
        self.assets_env.register('b', b)
        self.cmd_env.build(directory=self.path('some/path'))
        assert self.get('some/path/branch1/a') == 'FOO'
        assert self.get('some/path/branch2/b') == 'FOO'

    def test_custom_directory_not_supported_for_container_bundles(self):
        """This is at least true for now, we might want to do something
        about this."""
        b1 = MockBundle(output='b1')
        b2 = MockBundle(output='b2')
        b = MockBundle(b1, b2)
        self.assets_env.add(b)
        assert_raises(CommandError, self.cmd_env.build,
            directory=self.path('some/path'))

    def test_no_cache(self):
        """Test the no_cache option."""
        a = MockBundle(output='a')
        self.assets_env.register('a', a)
        self.cmd_env.build(no_cache=True)
        assert a.build_called[2].get('disable_cache') == True

        self.cmd_env.build(no_cache=False)
        assert a.build_called[2].get('disable_cache') == False

    def test_manifest(self):
        """Test the custom manifest option."""
        self.create_files(['media/sub/a'])
        a = Bundle('a', output='out')
        self.assets_env.register('a', a)

        # Use direct filepath - this will be relative to the cwd,
        # not the media directory.
        self.env.directory = self.path('media/sub')
        with working_directory(self.tempdir):
            self.cmd_env.build(manifest='bla')
            assert self.exists('bla')

        # Use prefix syntax
        self.cmd_env.build(manifest='file:miau')
        assert self.exists('media/sub/miau')

    def test_build_failure(self):
        """If one bundle fails to build, the command continues, but
        returns an error code in the end."""
        def failing_filter(*a, **kw):
            raise BuildError()
        self.create_files(['file'])
        a = Bundle('file', filters=failing_filter, output='outA')
        self.assets_env.register('a', a)
        b = Bundle('file', output='outB')
        self.assets_env.register('b', b)

        # build() returns an error code
        assert self.cmd_env.build() == 2
        # the second bundle will have been built, event though the first failed
        assert self.exists('outB')
        assert not self.exists('outA')


class TestWatchMixin(object):
    """Testing the watch command is hard."""

    def watch_loop(self):
        # Hooked into the loop of the ``watch`` command.
        # Allows stopping the thread.
        self.has_looped.set()
        time.sleep(0.01)
        if getattr(self, 'stopped', False):
            return True

    def start_watching(self):
        """Run the watch command in a thread."""
        self.has_looped = Event()
        t = Thread(target=self.cmd_env.watch, kwargs={'loop': self.watch_loop})
        t.daemon = True   # In case something goes wrong with stopping, this
        # will allow the test process to be end nonetheless.
        t.start()
        self.t = t
        # Wait for first iteration, which will initialize the mtimes. Only
        # after this will ``watch`` be able to detect changes.
        self.has_looped.wait(1)

    def stop_watching(self):
        """Stop the watch command thread."""
        assert self.t.isAlive() # If it has already ended, something is wrong
        self.stopped = True
        self.t.join(1)

    def __enter__(self):
        self.start_watching()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_watching()


class TestWatchCommand(TestWatchMixin, TestCLI):
    """This is a hard one to test.

    We run the watch command in a thread, and rely on its ``loop`` argument
    to stop the thread again.
    """

    default_files = {'in': 'foo', 'out': 'bar'}

    def setup(self):
        super(TestWatchCommand, self).setup()

        # Pay particular attention that the watch command works with auto_build
        # disabled (since normally this implies no use of the updater, but
        # obviously the command cannot pay attention to that).
        self.env.auto_build = False

    def test(self):
        # Register a bundle to watch
        bundle = self.mkbundle('in', output='out')
        self.env.register('test', bundle)
        now = self.setmtime('in', 'out')

        # Assert initial state
        assert self.get('out') == 'bar'

        # While watch is running, change input mtime
        with self:
            self.setmtime('in', mtime=now+10)
            # Allow watch to pick up the change
            time.sleep(0.2)

        # output file has been updated.
        assert self.get('out') == 'foo'

    def test_same_file_multiple_bundles(self):
        """[Bug] Test watch command can deal with the same file being part
        of multiple bundles. This was not always the case (github-127).
        """
        self.create_files({'out2': 'bar'})
        bundle1 = self.mkbundle('in', output='out')
        bundle2 = self.mkbundle('in', output='out2')
        self.env.register('test1', bundle1)
        self.env.register('test2', bundle2)
        now = self.setmtime('in', 'out', 'out2')

        # Assert initial state
        assert self.get('out') == 'bar'
        assert self.get('out2') == 'bar'

        # While watch is running, change input mtime
        with self:
            self.setmtime('in', mtime=now+10)
            # Allow watch to pick up the change
            time.sleep(0.2)

        # Both output files have been updated.
        assert self.get('out') == 'foo'
        assert self.get('out2') == 'foo'

    def test_initial_build(self):
        """The watch command also detects changes that were made while it was
        not running, and applies those right away on start.
        """
        # Register a bundle to watch
        bundle = self.mkbundle('in', output='out')
        self.env.register('test', bundle)

        # Mark the input file has changed before we even run the command.
        now = self.setmtime('in')
        self.setmtime('out', mtime=now-100)

        # Assert initial state
        assert self.get('out') == 'bar'

        # Run the watch command for a while, but don't make any changes.
        with self:
            time.sleep(0.2)

        # Output file has been updated, not due to a change detected by watch,
        # but because watch recognized the initial requirement for a build.
        assert self.get('out') == 'foo'


class TestCleanCommand(TestCLI):

    def test(self):
        self.create_files(['in'])
        self.env.cache = True

        bundle = self.mkbundle('in', output='out')
        self.env.add(bundle)

        bundle.build()
        assert self.exists('out')
        assert self.exists('.webassets-cache')

        self.cmd_env.clean()
        assert not self.exists('out')
        assert not self.exists('.webassets-cache')


class TestArgparseImpl(TestWatchMixin, TempEnvironmentHelper):
    """Test the argparse-based implementation of the CLI interface."""

    def test_no_env(self):
        """[Regression] If no env is hardcoded, nor one given via
        the commandline, we fail with a clean error.
        """
        impl = GenericArgparseImplementation(env=None)
        assert_raises(CommandError, impl.run_with_argv, ['build'])

    def test_watch_config_file(self):
        """The watch command has an eye on the config file. This is an
        extension to the base watch command."""
        try:
            import yaml
        except ImportError:
            raise SkipTest()

        self.cmd_env = CommandLineEnvironment(self.env, logging)
        self.cmd_env.commands['watch'] = \
            GenericArgparseImplementation.WatchCommand(
                self.cmd_env, argparse.Namespace(config=self.path('config.yml')))

        self.create_files({'in': 'foo'})
        template = """
directory: .
bundles:
  foo:
    contents:
        - in
    output: %s
"""
        self.create_files({'config.yml': template % 'outA'})

        with self:
            time.sleep(0.1)
            # Change the config file; this change is detected; we update
            # the timestamp explicitly or we might not have enough precision
            self.create_files({'config.yml': template % 'outB'})
            self.setmtime('config.yml', mod=100)
            time.sleep(0.2)

        # The second output file has been built
        assert self.get('outB') == 'foo'

    def test_watch_with_fixed_env_and_no_config(self):
        """[Regression[ The custom 'watch' command does not break if the
        CLI is initialized via fixed environment, instead of reading one from
        a configuration file.
        """
        self.cmd_env = CommandLineEnvironment(self.env, logging)
        self.cmd_env.commands['watch'] = \
            GenericArgparseImplementation.WatchCommand(
                self.cmd_env, argparse.Namespace())
        with self:
            time.sleep(0.1)
        # No errors occured


