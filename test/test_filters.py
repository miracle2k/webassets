import os
from nose.tools import assert_raises
from django.conf import settings
from django_assets.filter import BaseFilter, get_filter

# TODO: Add tests for all the builtin filters.


class TestBaseFilter:
    """Test the API ``BaseFilter`` provides to descendants.
    """

    def test_auto_name(self):
        """Test the automatic generation of the filter name.
        """
        assert type('Foo', (BaseFilter,), {}).name == 'foo'
        assert type('FooFilter', (BaseFilter,), {}).name == 'foo'
        assert type('FooBarFilter', (BaseFilter,), {}).name == 'foobar'

        assert type('Foo', (BaseFilter,), {'name': 'custom'}).name == 'custom'
        assert type('Foo', (BaseFilter,), {'name': None}).name == None

    def test_get_config(self):
        """Test the ``get_config`` helper.
        """
        get_config = BaseFilter().get_config

        # For the purposes of the following tests, we use a test
        # name which we expect to be undefined in both settings
        # and environment.
        NAME = 'FOO1234'
        assert not NAME in os.environ
        assert not hasattr(settings, NAME)

        # Test raising of error, and test not raising it.
        assert_raises(EnvironmentError, get_config, NAME)
        assert get_config(NAME, require=False) == None

        # Start by creating the value as a setting.
        setattr(settings, NAME, 'foo')
        assert get_config(NAME) == 'foo'
        assert get_config(setting=NAME, env=False) == 'foo'
        assert_raises(EnvironmentError, get_config, env=NAME)

        # Set the value in the environment as well.
        os.environ[NAME] = 'bar'
        # Ensure that settings take precedence.
        assert get_config(NAME) == 'foo'
        # Two different names can be supplied.
        assert not hasattr(settings, NAME*2)  # Must not yet exist.
        assert get_config(setting=NAME*2, env=NAME) == 'bar'

        # Unset the value in the settings. Note that due to the way
        # Django's settings object works, we need to access ``_wrapped``.
        delattr(settings._wrapped, NAME)
        assert get_config(NAME) == 'bar'
        assert get_config(env=NAME, setting=False) == 'bar'
        assert_raises(EnvironmentError, get_config, setting=NAME, env=False)

    def test_equality(self):
        """Test the ``unique`` method used to determine equality.
        """
        class TestFilter(BaseFilter):
            def unique(self):
                return getattr(self, 'token', None)
        f1 = TestFilter();
        f2 = TestFilter();

        # As long as the two tokens are equal, the filters are
        # considered to be the same.
        assert f1 == f2
        f1.token = 'foo'
        assert f1 != f2
        f2.token = 'foo'
        assert f1 == f2

        # However, unique() is only per class; two different filter
        # classes will never match...
        class AnotherFilter(TestFilter):
            # ...even if they have the same name.
            name = TestFilter.name
            def unique(self):
                return 'foo'
        g = AnotherFilter()
        assert f1 != g


def test_get_filter():
    """Test filter resolving.
    """
    # By name - here using one of the builtins.
    assert isinstance(get_filter('jsmin'), BaseFilter)
    assert_raises(ValueError, get_filter, 'notafilteractually')

    # By class.
    class MyFilter(BaseFilter): pass
    assert isinstance(get_filter(MyFilter), MyFilter)
    assert_raises(ValueError, get_filter, object())

    # Passing an instance doesn't do anything.
    f = MyFilter()
    assert id(get_filter(f)) == id(f)

    # Passing a lone callable will give us a a filter back as well.
    assert hasattr(get_filter(lambda: None), 'apply')
