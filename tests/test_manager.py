from nose.tools import assert_raises, with_setup

from webassets import AssetManager
from webassets.manager import RegisterError
from webassets import Bundle


class TestManager:

    def setup(self):
        self.m = AssetManager(None, None)

    def get(self, name='foo'):
        return self.m[name]

    def test_single_bundle(self):
        """Test self.m.registering a single ``Bundle`` object.
        """

        b = Bundle()
        self.m.register('foo', b)
        assert self.get() == b

    def test_new_bundle(self):
        """Test self.m.registering a new bundle on the fly.
        """

        b = Bundle()
        self.m.register('foo', b, 's2', 's3')
        assert b in self.get('foo').contents

        # Special case of using only a single, non-bundle source argument.
        self.m.register('footon', 's1')
        assert 's1' in self.get('footon').contents

        # Special case of specifying only a single bundle as a source, but
        # additional options - this also creates a wrapping bundle.
        self.m.register('foofighters', b, output="bar")
        assert b in self.get('foofighters').contents

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