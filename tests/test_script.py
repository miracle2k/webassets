"""TODO: This needs more testing. For now, we simply ensure that
the script can be at least invoked.
"""

import logging
from webassets import Environment, Bundle
from webassets.script import main, CommandLineEnvironment


def test_script():
    main([])


class MockBundle(Bundle):
    build_called = False
    def build(self, *a, **kw):
        self.build_called = True


class TestCLI(object):

    def setup(self):
        self.assets_env = Environment('', '')
        self.cmd_env = CommandLineEnvironment(self.assets_env, logging)

    def test_rebuild_container_bundles(self):
        """Test the rebuild command can deal with container bundles.
        """
        a = MockBundle(output='a')
        b1 = MockBundle(output='b1')
        b2 = MockBundle(output='b2')
        b = MockBundle(b1, b2)
        self.assets_env.add(a, b)

        self.cmd_env.rebuild()

        assert a.build_called
        assert not b.build_called
        assert b1.build_called
        assert b2.build_called

