import os

import pytest

from webassets import Environment
from webassets.env import RegisterError
from webassets import Bundle


class TestEnvApi(object):
    """General Environment functionality."""

    def setup_method(self):
        self.m = Environment(None, None)

    def test_register_single_bundle(self):
        """Test registering a single ``Bundle`` object.
        """
        b = Bundle()
        self.m.register('foo', b)
        assert self.m['foo'] == b

    def test_register_dict(self):
        """Register a bunch of bundles at once."""
        a = Bundle(); b = Bundle()
        self.m.register({'foo': a, 'bar': b})
        assert self.m['foo'] == a
        assert self.m['bar'] == b

    def test_register_new_bundle(self):
        """Test self.m.registering a new bundle on the fly.
        """

        b = Bundle()
        self.m.register('foo', b, 's2', 's3')
        assert b in self.m['foo'].contents

        # Special case of using only a single, non-bundle source argument.
        self.m.register('footon', 's1')
        assert 's1' in self.m['footon'].contents

        # Special case of specifying only a single bundle as a source, but
        # additional options - this also creates a wrapping bundle.
        self.m.register('foofighters', b, output="bar")
        assert b in self.m['foofighters'].contents

    def test_register_composed_bundle(self):
        """Test registering a bundle with `merge=False`
        """
        env = Environment('tests')

        env.register(
            'base1', 'helpers.py', 'test_ext/__init__.py',
            merge=False,
            output='build/%(name)s.%(version)s.css'
        )
        assert 'base1' not in env
        assert 'base1/helpers.py' in env
        assert 'base1/__init__.py' in env

        env.register(
            '', 'helpers.py', 'test_ext/__init__.py',
            merge=False,
            output='build/%(name)s.css'
        )
        assert 'helpers.py' in env
        assert '__init__.py' in env
        assert env['helpers.py'].output == 'build/helpers.css'
        assert env['__init__.py'].output == 'build/__init__.css'

        env.register(
            'base2', 'helper*.*',
            merge=False,
            output='build/%(name)s.%(ext)s'
        )
        assert 'base2/helpers.py' in env
        assert env['base2/helpers.py'].output == 'build/helpers.py'

        env.register(
            'base3', 'test_ext/__init__.py',
            merge=False,
            output='build/%(path)s.css'
        )
        assert env['base3/__init__.py'].output == 'build/test_ext/__init__.css'

    def test_register_composed_invalid(self):
        """Test registering a bundle with `merge=False`
        and invalid options.
        """
        env = Environment('tests')

        # No `output`
        pytest.raises(
            RegisterError, env.register,
            'base1', 'helpers.py', merge=False
        )

        # Nested bundle
        b = Bundle()
        pytest.raises(
            RegisterError, env.register,
            'base2', 'helpers.py', b, merge=False, output='a'
        )

    def test_register_invalid_call(self):
        """Test calling self.m.register with an invalid syntax.
        """
        pytest.raises(TypeError, self.m.register)
        pytest.raises(TypeError, self.m.register, 'one-argument-only')

    def test_register_duplicate(self):
        """Test name clashes.
        """

        b1 = Bundle()
        b2 = Bundle()

        self.m.register('foo', b1)

        # Multiple calls with the same name are ignored if the given bundle
        # is the same as originally passed.
        self.m.register('foo', b1)
        assert len(self.m) == 1

        # Otherwise, an error is raised.
        pytest.raises(RegisterError, self.m.register, 'foo', b2)
        pytest.raises(RegisterError, self.m.register, 'foo', 's1', 's2', 's3')

    def test_register_anon_bundle(self):
        """Self registering an anonymous bundle.
        """
        b = Bundle()
        self.m.add(b)
        assert len(self.m) == 1
        assert list(self.m) == [b]

    def test_contains(self):
        """Test __contains__.
        """
        b = Bundle()
        self.m.register('foo', b)
        assert 'foo' in self.m
        assert 'bar' not in self.m

    def test_bool_evaluation(self):
        """Test that environment evaluates to True in a boolean context.
        """
        env = Environment()
        assert env

    def test_url_and_directory(self):
        """The url and directory options are a bit special, because they
        are so essential.
        """

        # An environment can be constructed without given url or directory.
        env = Environment()
        # But then accessing them will fail, and with it most operations.
        pytest.raises(EnvironmentError, getattr, env, 'url')
        pytest.raises(EnvironmentError, getattr, env, 'directory')

        # Test constructing the environment with values for url and directory
        env = Environment('foo', 'bar')
        assert env.url == 'bar'
        assert env.config['directory'] == 'foo'
        assert env.directory == os.path.join(os.getcwd(), 'foo')

    def test_append_load_path(self):
        env = Environment()
        assert env.load_path == []

        env.append_path('foo', '/foo')
        assert env.load_path == ['foo']
        assert env.url_mapping == {'foo': '/foo'}

        # Works without path
        env.append_path('bar')
        assert env.load_path == ['foo', 'bar']
        assert env.url_mapping == {'foo': '/foo'}


class TestEnvConfig(object):
    """Custom config values through get_config/set_config.
    """

    def setup_method(self):
        self.m = Environment(None, None)

    def test_initial_values_override_defaults(self):
        """[Bug] If a dict of initial values are passed to the
        environment, they override any defaults the environment might
        want to set.
        """
        env = Environment(None, None, debug='foo')
        assert env.debug == 'foo'

    def test_basic(self):
        assert self.m.config.get('foo') is None
        self.m.config['foo'] = 'bar'
        assert self.m.config.get('foo') == 'bar'

    def test_case(self):
        """get_config() is case-insensitive.
        """
        self.m.config['FoO'] = 'bar'
        assert self.m.config.get('FOO') == 'bar'
        assert self.m.config.get('foo') == 'bar'
        assert self.m.config.get('fOO') == 'bar'


class TestSpecialProperties(object):
    """Certain environment options are special in that one may assign values
    as a string, and would receive object instances when accessing the property.
    """

    def setup_method(self):
        self.m = Environment('.', None)  # we won't create any files

    def test_versioner(self):
        from webassets.version import Version

        # Standard string values
        self.m.versions = 'timestamp'
        assert isinstance(self.m.config['versions'], str)
        assert isinstance(self.m.versions, Version)
        assert self.m.versions == 'timestamp'   # __eq__
        assert self.m.versions != 'hash'

        # False
        self.m.config['versions'] = False
        assert self.m.versions is None

        # Instance assign
        self.m.versions = instance = Version()
        assert self.m.versions == instance

        # Class assign
        self.m.versions = Version
        assert isinstance(self.m.versions, Version)

        # Invalid value
        self.m.versions = 'invalid-value'
        pytest.raises(ValueError, getattr, self.m, 'versions')

    def test_cache(self):
        from webassets.cache import BaseCache, FilesystemCache

        # True
        self.m.cache = True
        assert isinstance(self.m.config['cache'], type(True))
        assert isinstance(self.m.cache, BaseCache)
        assert self.m.cache == True   # __eq__
        assert self.m.cache != '/foo/path'

        # False value
        self.m.cache = False
        assert self.m.cache is None

        # Path
        self.m.cache = '/cache/dir'
        assert isinstance(self.m.cache, FilesystemCache)
        assert self.m.cache.directory == '/cache/dir'
        assert self.m.cache == True   # __eq__
        assert self.m.cache == '/cache/dir'  # __eq__

        # Instance assign
        self.m.cache = instance = BaseCache()
        assert self.m.cache == instance

        # Class assign
        self.m.cache = instance = BaseCache
        assert isinstance(self.m.cache, BaseCache)
