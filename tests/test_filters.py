import os
from nose.tools import assert_raises, with_setup, assert_equals
from nose import SkipTest
from webassets import Bundle, Environment
from webassets.filter import Filter, get_filter, register_filter
from helpers import BuildTestHelper

# Sometimes testing filter output can be hard if they generate
# unpredictable text like temp paths or timestamps. doctest has
# the same problem, so we just steal it's solution.
from doctest import _ellipsis_match as doctest_match


class TestFilter:
    """Test the API ``Filter`` provides to descendants.
    """

    def test_auto_name(self):
        """Test the automatic generation of the filter name.
        """
        assert type('Foo', (Filter,), {}).name == 'foo'
        assert type('FooFilter', (Filter,), {}).name == 'foo'
        assert type('FooBarFilter', (Filter,), {}).name == 'foobar'

        assert type('Foo', (Filter,), {'name': 'custom'}).name == 'custom'
        assert type('Foo', (Filter,), {'name': None}).name == None

    def test_get_config(self):
        """Test the ``get_config`` helper.
        """
        m = Environment(None, None)
        f = Filter()
        f.set_environment(m)
        get_config = f.get_config

        # For the purposes of the following tests, we use two test
        # names which we expect to be undefined in os.env.
        NAME = 'FOO%s' % id(object())
        NAME2 = 'FOO%s' % id(NAME)
        assert NAME != NAME2
        assert not NAME in os.environ and not NAME2 in os.environ

        try:
            # Test raising of error, and test not raising it.
            assert_raises(EnvironmentError, get_config, NAME)
            assert get_config(NAME, require=False) == None

            # Start with only the environment variable set.
            os.environ[NAME] = 'bar'
            assert get_config(NAME) == 'bar'
            assert get_config(env=NAME, setting=False) == 'bar'
            assert_raises(EnvironmentError, get_config, setting=NAME, env=False)

            # Set the value in the environment as well.
            m.config[NAME] = 'foo'
            # Ensure that settings take precedence.
            assert_equals(get_config(NAME), 'foo')
            # Two different names can be supplied.
            assert get_config(setting=NAME2, env=NAME) == 'bar'

            # Unset the env variable, now with only the setting.
            del os.environ[NAME]
            assert get_config(NAME) == 'foo'
            assert get_config(setting=NAME, env=False) == 'foo'
            assert_raises(EnvironmentError, get_config, env=NAME)
        finally:
            if NAME in os.environ:
                del os.environ[NAME]

    def test_equality(self):
        """Test the ``unique`` method used to determine equality.
        """
        class TestFilter(Filter):
            def unique(self):
                return getattr(self, 'token', 'bar')
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
            # ...provided they have a different name.
            name = TestFilter.name + '_2'
            def unique(self):
                return 'foo'
        g = AnotherFilter()
        assert f1 != g


def test_register_filter():
    """Test registration of custom filters.
    """
    # Needs to be a ``Filter`` subclass.
    assert_raises(ValueError, register_filter, object)

    # A name is required.
    class MyFilter(Filter):
        name = None
        def output(self, *a, **kw): pass
    assert_raises(ValueError, register_filter, MyFilter)

    # The same filter cannot be registered under multiple names.
    MyFilter.name = 'foo'
    register_filter(MyFilter)
    MyFilter.name = 'bar'
    register_filter(MyFilter)

    # But the same name cannot be registered multiple times.
    assert_raises(KeyError, register_filter, MyFilter)

    # A filter needs to have at least one of the input or output methods.
    class BrokenFilter(Filter):
        name = 'broken'
    assert_raises(TypeError, register_filter, BrokenFilter)


def test_get_filter():
    """Test filter resolving.
    """
    # By name - here using one of the builtins.
    assert isinstance(get_filter('jsmin'), Filter)
    assert_raises(ValueError, get_filter, 'notafilteractually')

    # By class.
    class MyFilter(Filter): pass
    assert isinstance(get_filter(MyFilter), MyFilter)
    assert_raises(ValueError, get_filter, object())

    # Passing an instance doesn't do anything.
    f = MyFilter()
    assert id(get_filter(f)) == id(f)

    # Passing a lone callable will give us a a filter back as well.
    assert hasattr(get_filter(lambda: None), 'output')

    # Arguments passed to get_filter are used for instance creation.
    assert get_filter('sass', scss=True).use_scss == True
    # However, this is not allowed when a filter instance is passed directly,
    # or a callable object.
    assert_raises(AssertionError, get_filter, f, 'test')
    assert_raises(AssertionError, get_filter, lambda: None, 'test')


class TestBuiltinFilters(BuildTestHelper):
    """
    TODO: Add tests for all the builtin filters.
    """

    default_files = {
        'foo.css': """
            h1  {
                font-family: "Verdana"  ;
                color: #FFFFFF;
            }
        """,
        'foo.clevercss': """a:
            color: #fff.darken(50%)
        """,
        'foo.coffee': "alert \"I knew it!\" if elvis?"
    }

    def test_cssrewrite(self):
        self.create_files({'in.css': '''h1 { background: url(sub/icon.png) }'''})
        self.create_directories('g')
        self.mkbundle('in.css', filters='cssrewrite', output='g/out.css').build()
        assert self.get('g/out.css') == '''h1 { background: url(../sub/icon.png) }'''

    def test_cssrewrite_change_folder(self):
        """Test the replace mode of the cssrewrite filter.
        """
        self.create_files({'in.css': '''h1 { background: url(old/sub/icon.png) }'''})
        try:
            from collections import OrderedDict
        except ImportError:
            # Without OrderedDict available, use a simplified version
            # of this test.
            cssrewrite = get_filter('cssrewrite', replace=dict((
                ('o', '/error/'),       # o does NOT match the old/ dir
                ('old', '/new/'),       # this will match
            )))
        else:
            cssrewrite = get_filter('cssrewrite', replace=OrderedDict((
                ('o', '/error/'),       # o does NOT match the old/ dir
                ('old', '/new/'),       # this will match
                ('old/sub', '/error/'), # the first match is used, so this won't be
                ('new', '/error/'),     # neither will this one match
            )))
        self.mkbundle('in.css', filters=cssrewrite, output='out.css').build()
        assert self.get('out.css') == '''h1 { background: url(/new/sub/icon.png) }'''

    def test_cssmin(self):
        try:
            self.mkbundle('foo.css', filters='cssmin', output='out.css').build()
            assert self.get('out.css') == """h1{font-family:"Verdana";color:#FFF}"""
        except EnvironmentError:
            # cssmin is not installed, that's ok.
            raise SkipTest()

    def test_clevercss(self):
        try:
            import clevercss
        except ImportError:
            raise SkipTest()
        clevercss = get_filter('clevercss')
        self.mkbundle('foo.clevercss', filters=clevercss, output='out.css').build()
        assert self.get('out.css') == """a {
  color: #7f7f7f;
}"""

    def test_coffeescript(self):
        coffeescript = get_filter('coffeescript')
        self.mkbundle('foo.coffee', filters=coffeescript, output='out.js').build()
        assert self.get('out.js') == """if (typeof elvis != "undefined" && elvis !== null) {
  alert("I knew it!");
}
"""


class TestSass(BuildTestHelper):

    default_files = {
        'foo.css': """
            h1  {
                font-family: "Verdana"  ;
                color: #FFFFFF;
            }
        """,
        'foo.sass': """h1
            font-family: "Verdana"
            color: #FFFFFF
        """,
    }

    def test_sass(self):
        sass = get_filter('sass', debug_info=False)
        self.mkbundle('foo.sass', filters=sass, output='out.css').build()
        assert self.get('out.css') == """/* line 1 */\nh1 {\n  font-family: "Verdana";\n  color: white;\n}\n"""

    def test_sass_import(self):
        """Test referencing other files in sass.
        """
        sass = get_filter('sass', debug_info=False)
        self.create_files({'import-test.sass': '''@import foo.sass'''})
        self.mkbundle('import-test.sass', filters=sass, output='out.css').build()
        assert self.get('out.css') == """/* line 1, ./foo.sass */\nh1 {\n  font-family: "Verdana";\n  color: white;\n}\n"""

    def test_scss(self):
        # SCSS is a CSS superset, should be able to compile the CSS file just fine
        scss = get_filter('scss', debug_info=False)
        self.mkbundle('foo.css', filters=scss, output='out.css').build()
        assert self.get('out.css') == """/* line 2 */\nh1 {\n  font-family: "Verdana";\n  color: #FFFFFF;\n}\n"""

    def test_debug_info_option(self):
        # The debug_info argument to the sass filter can be configured via
        # a global SASS_DEBUG_INFO option.
        self.m.config['SASS_DEBUG_INFO'] = False
        self.mkbundle('foo.sass', filters=get_filter('sass'), output='out.css').build()
        assert not '-sass-debug-info' in self.get('out.css')

        # However, an instance-specific debug_info option takes precedence.
        self.mkbundle('foo.sass', filters=get_filter('sass', debug_info=True), output='out2.css').build()
        assert '-sass-debug-info' in self.get('out2.css')


class TestCompass(BuildTestHelper):

    default_files = {
        'foo.scss': """
            h1  {
                font-family: "Verdana"  ;
                color: #FFFFFF;
            }
        """,
        'import.scss': """
        @import "foo.scss";
        """,
        'foo.sass': """h1
            font-family: "Verdana"
            color: #FFFFFF
        """
    }

    def test_compass(self):
        self.mkbundle('foo.sass', filters='compass', output='out.css').build()
        print self.get('out.css')
        assert doctest_match("""/* ... */\nh1 {\n  font-family: "Verdana";\n  color: white;\n}\n""", self.get('out.css'))

    def test_compass_with_imports(self):
        self.mkbundle('import.scss', filters='compass', output='out.css').build()
        assert doctest_match("""/* ... */\nh1 {\n  font-family: "Verdana";\n  color: #FFFFFF;\n}\n""", self.get('out.css'))

    def test_compass_with_scss(self):
        # [bug] test compass with scss files
        self.mkbundle('foo.scss', filters='compass', output='out.css').build()
        assert doctest_match("""/* ... */\nh1 {\n  font-family: "Verdana";\n  color: #FFFFFF;\n}\n""", self.get('out.css'))