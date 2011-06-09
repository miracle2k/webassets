from nose.tools import assert_raises, with_setup

from webassets import Environment
from webassets.env import RegisterError
from webassets import Bundle


class TestEnvApi:
    """General Environment functionality."""

    def setup(self):
        self.m = Environment(None, None)

    def test_single_bundle(self):
        """Test self.m.registering a single ``Bundle`` object.
        """ 
        b = Bundle()
        self.m.register('foo', b)
        assert self.m['foo'] == b

    def test_new_bundle(self):
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

    def test_invalid_call(self):
        """Test calling self.m.register with an invalid syntax.
        """
        assert_raises(TypeError, self.m.register)
        assert_raises(TypeError, self.m.register, 'one-argument-only')

    def test_duplicate(self):
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
        assert_raises(RegisterError, self.m.register, 'foo', b2)
        assert_raises(RegisterError, self.m.register, 'foo', 's1', 's2', 's3')

    def test_anon_bundle(self):
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
        assert not 'bar' in self.m


class TestEnvConfig:
    """Custom config values through get_config/set_config.
    """

    def setup(self):
        self.m = Environment(None, None)

    def test_initial_values_override_defaults(self):
        """[Bug] If a dict of initial values are passed to the
        environment, they override any defaults the environment might
        want to set.
        """
        env = Environment(None, None, debug='foo')
        assert env.debug == 'foo'

    def test_basic(self):
        assert self.m.config.get('foo') == None
        self.m.config['foo'] = 'bar'
        assert self.m.config.get('foo') == 'bar'

    def test_case(self):
        """get_config() is case-insensitive.
        """
        self.m.config['FoO'] = 'bar'
        assert self.m.config.get('FOO') == 'bar'
        assert self.m.config.get('foo') == 'bar'
        assert self.m.config.get('fOO') == 'bar'


class TestSpecialProperties:
    """Certain environment options are special in that one may assign
    values as a string, and would receive object instances when
    accessing the property.
    """

    def setup(self):
        self.m = Environment('.', None)  # we won't create any files

    def test_updater(self):
        from webassets.updater import BaseUpdater

        # Standard string values
        self.m.updater = 'always'
        assert isinstance(self.m.config['updater'], basestring)
        assert isinstance(self.m.updater, BaseUpdater)
        assert self.m.updater == 'always'   # __eq__
        assert self.m.updater != 'timestamp'

        # False
        self.m.config['updater'] = False
        assert self.m.updater is None

        # Instance assign
        self.m.updater = instance = BaseUpdater()
        assert self.m.updater == instance

        # Class assign
        self.m.updater = BaseUpdater
        assert isinstance(self.m.updater, BaseUpdater)

        # Invalid value
        self.m.updater = 'invalid-value'
        assert_raises(ValueError, getattr, self.m, 'updater')

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
