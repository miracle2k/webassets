"""TODO: More commands need testing.

TODO: Looking at how we need to make the MockBundle write to``output``,
I wonder whether I shouldn't just do full-stack tests here instead of mocking.
"""

from __future__ import with_statement

import logging
from nose.tools import assert_raises
from webassets import Bundle
from webassets.script import main, CommandLineEnvironment, CommandError
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
        a.on_build = lambda *a, **kw: kw.get('output').write('FOO')
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
        a.on_build = lambda *a, **kw: kw.get('output').write('FOO')
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
