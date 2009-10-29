from nose.tools import assert_raises, with_setup

from django_assets import register
from django_assets.registry import _REGISTRY, RegistryError, reset
from django_assets import Bundle


def _get(i='foo'):
    return _REGISTRY[i]


@with_setup(reset)
def test_single_bundle():
    """Test registering a single ``Bundle`` object.
    """

    b = Bundle()
    register('foo', b)
    assert _get() == b


@with_setup(reset)
def test_new_bundle():
    """Test registering a new bundle on the fly.
    """

    b = Bundle()
    register('foo', b, 's2', 's3')
    assert b in _get('foo').contents

    # Special case of using only a single, non-bundle source argument.
    register('footon', 's1')
    assert 's1' in _get('footon').contents

    # Special case of specifying only a single bundle as a source, but
    # additional options - this also creates a wrapping bundle.
    register('foofighters', b, output="bar")
    assert b in _get('foofighters').contents


@with_setup(reset)
def test_invalid_call():
    """Test calling register with an invalid syntax.
    """
    assert_raises(TypeError, register)
    assert_raises(TypeError, register, 'one-argument-only')


@with_setup(reset)
def test_duplicate():
    """Test name clashes.
    """

    b1 = Bundle()
    b2 = Bundle()

    register('foo', b1)

    # Multiple calls with the same name are ignored if the given bundle
    # is the same as originally passed.
    register('foo', b1)
    assert len(_REGISTRY) == 1

    # Otherwise, an error is raised.
    assert_raises(RegistryError, register, 'foo', b2)
    assert_raises(RegistryError, register, 'foo', 's1', 's2', 's3')