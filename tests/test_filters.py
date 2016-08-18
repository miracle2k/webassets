# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import with_statement

import os
import os.path
from contextlib import contextmanager
from nose.tools import assert_raises, assert_equal, assert_true
from nose import SkipTest
from mock import patch, Mock, DEFAULT
from distutils.spawn import find_executable
import re
from webassets.utils import StringIO
from webassets import Environment
from webassets.exceptions import FilterError
from webassets.filter import (
    Filter, ExternalTool, get_filter, register_filter, unique_modules)
from webassets.filter.compass import CompassConfig
from webassets.bundle import ContextWrapper
from .helpers import TempEnvironmentHelper

# Sometimes testing filter output can be hard if they generate
# unpredictable text like temp paths or timestamps. doctest has
# the same problem, so we just steal its solution.
from doctest import _ellipsis_match as doctest_match


import platform
PYPY = platform.python_implementation() == 'PyPy'


@contextmanager
def os_environ_sandbox():
    backup = os.environ.copy()
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(backup)


class TestFilterBaseClass(object):
    """Test the API ``Filter`` provides to descendants.
    """

    def test_auto_name(self):
        """Filter used to have an auto-generated name assigned, but this
        is no longer the case.
        """
        assert type('Foo', (Filter,), {}).name is None
        assert type('Foo', (Filter,), {'name': 'custom'}).name == 'custom'
        assert type('Foo', (Filter,), {'name': None}).name is None

    def test_options(self):
        """Test option declaration.
        """
        class TestFilter(Filter):
            options = {
                'attr1': 'ATTR1',
                'attr2': ('secondattr', 'ATTR2'),
                'attr3': (False, 'ATTR3'),
                'attr4': ('attr4', False),
            }

        # Test __init__ arguments
        assert TestFilter(attr1='foo').attr1 == 'foo'
        assert TestFilter(secondattr='foo').attr2 == 'foo'
        assert_raises(TypeError, TestFilter, attr3='foo')
        assert TestFilter(attr4='foo').attr4 == 'foo'

        # Test config vars
        env = Environment(None, None)
        env.config['attr1'] = 'bar'
        env.config['attr4'] = 'bar'
        f = TestFilter(); f.ctx = ContextWrapper(env); f.setup()
        assert f.attr1 == 'bar'
        assert f.attr4 is None    # Was configured to not support env

    def test_get_config(self):
        """Test the ``get_config`` helper.
        """
        m = Environment(None, None)
        f = Filter()
        f.set_context(ContextWrapper(m))
        get_config = f.get_config

        # For the purposes of the following tests, we use two test
        # names which we expect to be undefined in os.env.
        NAME = 'FOO%s' % id(object())
        NAME2 = 'FOO%s' % id(NAME)
        assert NAME != NAME2
        assert not NAME in os.environ and not NAME2 in os.environ

        with os_environ_sandbox():
            # Test raising of error, and test not raising it.
            assert_raises(EnvironmentError, get_config, NAME)
            assert get_config(NAME, require=False) is None

            # Start with only the environment variable set.
            os.environ[NAME] = 'bar'
            assert get_config(NAME) == 'bar'
            assert get_config(env=NAME, setting=False) == 'bar'
            assert_raises(EnvironmentError, get_config, setting=NAME, env=False)

            # Set the value in the environment as well.
            m.config[NAME] = 'foo'
            # Ensure that settings take precedence.
            assert_equal(get_config(NAME), 'foo')
            # Two different names can be supplied.
            assert get_config(setting=NAME2, env=NAME) == 'bar'

            # Unset the env variable, now with only the setting.
            del os.environ[NAME]
            assert get_config(NAME) == 'foo'
            assert get_config(setting=NAME, env=False) == 'foo'
            assert_raises(EnvironmentError, get_config, env=NAME)

    def test_getconfig_os_env_types(self):
        """Test type conversion for values read from the environment.
        """
        m = Environment(None, None)
        f = Filter()
        f.set_context(ContextWrapper(m))
        get_config = f.get_config

        with os_environ_sandbox():
            os.environ['foo'] = 'one,two\,three'
            assert list(get_config(env='foo', type=list)) == ['one', 'two,three']

            # Make sure the split is not applied to env config values
            m.config['foo'] = 'one,two\,three'
            assert get_config(setting='foo', type=list) == 'one,two\,three'

    def test_equality(self):
        """Test the ``unique`` method used to determine equality.
        """
        class TestFilter(Filter):
            name = 'test'
            def unique(self):
                return getattr(self, 'token', 'bar')
        f1 = TestFilter()
        f2 = TestFilter()

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


class TestExternalToolClass(object):
    """Test the API ``Filter`` provides to descendants.
    """

    class MockTool(ExternalTool):
        method = None
        def subprocess(self, argv, out, data=None):
            self.__class__.result = \
                argv, data.getvalue() if data is not None else data

    def setup(self):
        if not hasattr(str, 'format'):
            # A large part of this functionality is not available on Python 2.5
            raise SkipTest()
        self.patcher = patch('subprocess.Popen')
        self.popen = self.patcher.start()
        self.popen.return_value = Mock()
        self.popen.return_value.communicate = Mock()

    def teardown(self):
        self.patcher.stop()

    def test_argv_variables(self):
        """In argv, a number of placeholders can be used. Ensure they work."""
        class Filter(self.MockTool):
            argv = [
                # The filter instance
                '{self.__class__.__name__}',
                # Keyword and positional args to filter method
                '{kwarg}', '{0.closed}',
                # Special placeholders that are passed through
                '{input}', '{output}']
        Filter().output(StringIO('content'), StringIO(), kwarg='value')
        assert Filter.result == (
            ["Filter", 'value', 'False', '{input}', '{output}'], 'content')

    def test_method_input(self):
        """The method=input."""
        class Filter(self.MockTool):
            method = 'input'
        assert getattr(Filter, 'output') is None
        assert getattr(Filter, 'open') is None
        Filter().input(StringIO(u'błä'), StringIO())
        assert Filter.result == ([], u'błä')

    def test_method_output(self):
        """The method=output."""
        class Filter(self.MockTool):
            method = 'output'
        assert getattr(Filter, 'input') is None
        assert getattr(Filter, 'open') is None
        Filter().output(StringIO(u'błä'), StringIO())
        assert Filter.result == ([], u'błä')

    def test_method_open(self):
        """The method=open."""
        class Filter(self.MockTool):
            method = 'open'
        assert getattr(Filter, 'output') is None
        assert getattr(Filter, 'input') is None
        Filter().open(StringIO(), 'filename')
        assert Filter.result == ([], None)

    def test_method_invalid(self):
        assert_raises(AssertionError,
            type, 'Filter', (ExternalTool,), {'method': 'foobar'})

    def test_no_method(self):
        """When no method is given."""
        # If no method and no argv is given, no method will be implemented
        class Filter(ExternalTool):
            pass
        assert getattr(Filter, 'output') is None
        assert getattr(Filter, 'open') is None
        assert getattr(Filter, 'input') is None

        # If no method, but argv is given, the output  method will be
        # implemented by default.
        class Filter(ExternalTool):
            argv = ['app']
        assert not getattr(Filter, 'output') is None
        assert getattr(Filter, 'open') is None
        assert getattr(Filter, 'input') is None

        # If method is set to None, all method will remain available
        class Filter(ExternalTool):
            method = None
        assert not getattr(Filter, 'output') is None
        assert not getattr(Filter, 'open') is None
        assert not getattr(Filter, 'input') is None

    def test_subsubclass(self):
        """Test subclassing a class based on ExternalTool again.

        The ``method`` argument no longer has any effect if already used
        in parent class.
        """
        class Baseclass(ExternalTool):
            method = 'open'
        class Subclass(Baseclass):
            method = 'input'
        assert getattr(Baseclass, 'output') is None
        assert getattr(Baseclass, 'input') is None
        assert not getattr(Baseclass, 'open') is None
        # No all is None - very useless.
        assert getattr(Subclass, 'output') is None
        assert getattr(Subclass, 'input') is None
        assert not getattr(Subclass, 'open') is None

    def test_method_no_override(self):
        """A subclass may implement specific methods itself; if it
        does, the base class must not override those with None."""
        class Filter(self.MockTool):
            method = 'open'
            def input(self, _in, out, **kw):
                pass
        assert not getattr(Filter, 'input') is None
        assert getattr(Filter, 'output') is None

    def test_subprocess(self):
        """Instead of the ``argv`` shortcut, subclasses can also use the
        ``subprocess`` helper manually.
        """

        class Filter(ExternalTool): pass

        # Without stdin data
        self.popen.return_value.returncode = 0
        self.popen.return_value.communicate.return_value = [b'stdout', b'stderr']
        out = StringIO()
        Filter.subprocess(['test'], out)
        assert out.getvalue() == 'stdout'
        self.popen.return_value.communicate.assert_called_with(None)

        # With stdin data
        self.popen.reset_mock()
        self.popen.return_value.returncode = 0
        self.popen.return_value.communicate.return_value = [b'stdout', b'stderr']
        out = StringIO()
        Filter.subprocess(['test'], out, data='data')
        assert out.getvalue() == 'stdout'
        self.popen.return_value.communicate.assert_called_with(b'data')

        # With error
        self.popen.return_value.returncode = 1
        self.popen.return_value.communicate.return_value = [b'stdout', b'stderr']
        assert_raises(FilterError, Filter.subprocess, ['test'], StringIO())

    def test_input_var(self):
        """Test {input} variable."""
        class Filter(ExternalTool): pass
        self.popen.return_value.returncode = 0
        self.popen.return_value.communicate.return_value = [b'stdout', b'stderr']

        # {input} creates an input file
        intercepted = {}
        def check_input_file(argv,  **kw):
            intercepted['filename'] = argv[0]
            with open(argv[0], 'rb') as f:
                # File has been generated with input data
                assert f.read() == b'foo\xc3\xb1'
            return DEFAULT
        self.popen.side_effect = check_input_file
        Filter.subprocess(['{input}'], StringIO(), data=u'fooñ')
        # No stdin was passed
        self.popen.return_value.communicate.assert_called_with(None)
        # File has been deleted
        assert not os.path.exists(intercepted['filename'])

        # {input} requires input data
        assert_raises(ValueError, Filter.subprocess, ['{input}'], StringIO())

    def test_output_var(self):
        class Filter(ExternalTool): pass
        self.popen.return_value.returncode = 0
        self.popen.return_value.communicate.return_value = ['stdout', 'stderr']

        # {output} creates an output file
        intercepted = {}
        def fake_output_file(argv,  **kw):
            intercepted['filename'] = argv[0]
            with open(argv[0], 'w') as f:
                f.write('batñ')
            return DEFAULT
        self.popen.side_effect = fake_output_file
        # We get the result we generated in the hook above
        out = StringIO(u'')
        Filter.subprocess(['{output}'], out)
        assert out.getvalue() == u'batñ'
        # File has been deleted
        assert not os.path.exists(intercepted['filename'])

    def test_output_moved(self):
        class Filter(ExternalTool): pass
        self.popen.return_value.returncode = 0
        self.popen.return_value.communicate.return_value = ['stdout', 'stderr']

        # {output} creates an output
        # this test *moves* the file into the target location, and
        # tests the fix to issue #286
        intercepted = {}
        def fake_output_file(argv,  **kw):
            intercepted['filename'] = argv[0]
            with open(argv[0] + '.tmp', 'w') as f:
                f.write('bat')
            import shutil
            shutil.move(argv[0] + '.tmp', argv[0])
            return DEFAULT
        self.popen.side_effect = fake_output_file
        # We get the result we generated in the hook above
        out = StringIO()
        Filter.subprocess(['{output}'], out)
        assert out.getvalue() == 'bat'
        # File has been deleted
        assert not os.path.exists(intercepted['filename'])


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

    # We should be able to register a filter with a name.
    MyFilter.name = 'foo'
    register_filter(MyFilter)

    # A filter should be able to override a pre-registered filter of the same
    # name.
    class OverrideMyFilter(Filter):
        name = 'foo'
        def output(self, *a, **kw): pass
    register_filter(OverrideMyFilter)
    assert_true(isinstance(get_filter('foo'), OverrideMyFilter))


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


def test_callable_filter():
    """Simple callables can be used as filters.

    Regression: Ensure that they actually work.
    """
    # Note how this filter specifically does not receive any **kwargs.
    def my_filter(_in, out):
        assert _in.read() == 'initial value'
        out.write('filter was here')
    with TempEnvironmentHelper() as helper:
        helper.create_files({'in': 'initial value'})
        b = helper.mkbundle('in', filters=my_filter, output='out')
        b.build()
        assert helper.get('out') == 'filter was here'


class TestBuiltinFilters(TempEnvironmentHelper):

    default_files = {
        'foo.css': u"""
        /* Cômment wíth sóme Ünicòde */
            h1  {
                font-family: "Verdana"  ;
                color: #FFFFFF;
            }
        """,
        'foo.js': u"""
        // Cômment wíth sóme Ünicòde
        function foo(bar) {
            var dummy;
            document.write ( bar ); /* Write */
            var a = "Ünícôdè";
        }
        """,
        'foo2.js': """
        more();
        """
    }

    def test_cssmin(self):
        try:
            self.mkbundle('foo.css', filters='cssmin', output='out.css').build()
        except EnvironmentError:
            # cssmin is not installed, that's ok.
            raise SkipTest()
        assert self.get('out.css') == """h1{font-family:"Verdana";color:#FFF}"""

    def test_cssutils(self):
        try:
            import cssutils
        except ImportError:
            raise SkipTest()
        self.mkbundle('foo.css', filters='cssutils', output='out.css').build()
        assert self.get('out.css') == """h1{font-family:"Verdana";color:#FFF}"""

    def test_clevercss(self):
        try:
            import clevercss
        except ImportError:
            raise SkipTest()
        self.create_files({'in': """a:\n    color: #fff.darken(50%)"""})
        self.mkbundle('in', filters='clevercss', output='out.css').build()
        assert self.get('out.css') == """a {\n  color: #7f7f7f;\n}"""

    def test_uglifyjs_ascii(self):
        if not find_executable('uglifyjs'):
            raise SkipTest()
        self.mkbundle('foo2.js', filters='uglifyjs', output='out.js').build()
        assert self.get('out.js') == 'more();'

    def test_uglifyjs_unicode(self):
        if not find_executable('uglifyjs'):
            raise SkipTest()
        self.mkbundle('foo.js', filters='uglifyjs', output='out.js').build()
        assert self.get('out.js') == 'function foo(bar){var dummy;document.write(bar);var a="Ünícôdè"}'

    def test_uglifyjs_ascii_and_unicode(self):
        if not find_executable('uglifyjs'):
            raise SkipTest()
        self.mkbundle('foo.js', 'foo2.js', filters='uglifyjs', output='out.js').build()
        assert self.get('out.js') == 'function foo(bar){var dummy;document.write(bar);var a="Ünícôdè"}more();'

    def test_slimit_ascii(self):
        try:
            self.mkbundle('foo2.js', filters='slimit', output='out.js').build()
        except EnvironmentError:
            raise SkipTest("slimit is not installed")
        assert self.get('out.js') == 'more();'

    def test_slimit_unicode(self):
        try:
            self.mkbundle('foo.js', filters='slimit', output='out.js').build()
        except EnvironmentError:
            raise SkipTest("slimit is not installed")
        assert self.get('out.js') == 'function foo(bar){var dummy;document.write(bar);var a="Ünícôdè";}'

    def test_slimit_ascii_and_unicode(self):
        try:
            self.mkbundle('foo.js', 'foo2.js', filters='slimit', output='out.js').build()
        except EnvironmentError:
            raise SkipTest("slimit is not installed")
        assert self.get('out.js') == 'function foo(bar){var dummy;document.write(bar);var a="Ünícôdè";}more();'

    def test_less_ruby(self):
        # TODO: Currently no way to differentiate the ruby lessc from the
        # JS one. Maybe the solution is just to remove the old ruby filter.
        raise SkipTest()
        self.mkbundle('foo.css', filters='less_ruby', output='out.css').build()
        assert self.get('out.css') == 'h1 {\n  font-family: "Verdana";\n  color: #ffffff;\n}\n'

    def test_jsmin(self):
        try:
            import jsmin
        except ImportError:
            raise SkipTest()
        self.mkbundle('foo.js', filters='jsmin', output='out.js').build()
        assert self.get('out.js') in (
            # Builtin jsmin
            "\nfunction foo(bar){var dummy;document.write(bar);var a=\"Ünícôdè\"}",
            # jsmin from PyPI
            ' function foo(bar){var dummy;document.write(bar);var a="\xc3\x9cn\xc3\xadc\xc3\xb4d\xc3\xa8";}',
            # jsmin from v8
            '\n\nfunction foo(a){\nvar b;\ndocument.write(a);\nvar c="\xc3\x9cn\xc3\xadc\xc3\xb4d\xc3\xa8";\n}\n\n',
        )

    def test_rjsmin(self):
        try:
            import rjsmin
        except ImportError:
            raise SkipTest()
        self.mkbundle('foo.js', filters='rjsmin', output='out.js').build()
        assert self.get('out.js') == 'function foo(bar){var dummy;document.write(bar);var a="\xc3\x9cn\xc3\xadc\xc3\xb4d\xc3\xa8";}'

    def test_jspacker(self):
        self.mkbundle('foo.js', filters='jspacker', output='out.js').build()
        assert self.get('out.js').startswith('eval(function(p,a,c,k,e,d)')

    def test_yui_js(self):
        try:
            import yuicompressor
        except ImportError:
            raise SkipTest()
        self.mkbundle('foo.js', filters='yui_js', output='out.js').build()
        assert self.get('out.js') == 'function foo(c){var d;document.write(c);var b="Ünícôdè"};'

    def test_yui_css(self):
        try:
            import yuicompressor
        except ImportError:
            raise SkipTest()
        self.mkbundle('foo.css', filters='yui_css', output='out.css').build()
        assert self.get('out.css') == """h1{font-family:"Verdana";color:#fff}"""

    def test_cleancss(self):
        if not find_executable('cleancss'):
            raise SkipTest()
        self.mkbundle('foo.css', filters='cleancss', output='out.css').build()
        assert self.get('out.css') == 'h1{font-family:Verdana;color:#FFF}'

    def test_cssslimmer(self):
        try:
            import slimmer
        except ImportError:
            raise SkipTest()
        self.mkbundle('foo.css', filters='css_slimmer', output='out.css').build()
        assert self.get('out.css') == 'h1{font-family:"Verdana";color:#FFF}'

    def test_stylus(self):
        if not find_executable('stylus'):
            raise SkipTest()
        self.create_files({'in': """a\n  width:100px\n  height:(@width/2)"""})
        self.mkbundle('in', filters='stylus', output='out.css').build()
        assert self.get('out.css') == """a {\n  width: 100px;\n  height: 50px;\n}\n\n"""

    def test_find_pyc_files( self ):
        self.create_files({'test.pyc':'testing', 'test.py':'blue', 'boo.pyc':'boo'})
        modules = list( unique_modules(self.tempdir))
        assert modules == ['boo','test'],modules

    def test_find_packages( self ):
        self.create_files({'moo/__init__.pyc':'testing','voo/__init__.py':'testing'})
        modules = list( unique_modules(self.tempdir))
        assert modules == ['moo','voo'],modules


class TestCSSPrefixer(TempEnvironmentHelper):

    def setup(self):
        try:
            import cssprefixer
        except ImportError:
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test(self):
        self.create_files({'in': """a { border-radius: 1em; }"""})
        self.mkbundle('in', filters='cssprefixer', output='out.css').build()
        assert self.get('out.css') == 'a {\n    -moz-border-radius: 1em;\n    -webkit-border-radius: 1em;\n    border-radius: 1em\n    }'

    def test_encoding(self):
        self.create_files({'in': u"""a { content: '\xe4'; }""".encode('utf8')})
        self.mkbundle('in', filters='cssprefixer', output='out.css').build()
        assert self.get('out.css') == 'a {\n    content: "\xc3\xa4"\n    }'


class TestCoffeeScript(TempEnvironmentHelper):

    def setup(self):
        if not find_executable('coffee'):
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test_default_options(self):
        self.create_files({'in': "alert \"I knew it!\" if elvis?"})
        self.mkbundle('in', filters='coffeescript', output='out.js').build()
        assert self.get('out.js') == """if (typeof elvis !== "undefined" && elvis !== null) {\n  alert("I knew it!");\n}\n"""

    def test_bare_option(self):
        self.env.config['COFFEE_NO_BARE'] = True
        self.create_files({'in': "@a = 1"})
        self.mkbundle('in', filters='coffeescript', output='out.js').build()
        assert self.get('out.js') == '(function() {\n  this.a = 1;\n\n}).call(this);\n'

        self.env.config['COFFEE_NO_BARE'] = False
        self.create_files({'in': "@a = 1"})
        self.mkbundle('in', filters='coffeescript', output='out.js').build(force=True)
        assert self.get('out.js') == 'this.a = 1;\n'


class TestJinja2(TempEnvironmentHelper):

    def setup(self):
        try:
            import jinja2
        except ImportError:
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test_default_options(self):
        self.create_files({'in': """Hi there, {{ name }}!"""})
        self.mkbundle('in', filters='jinja2', output='out.template').build()
        assert self.get('out.template') == """Hi there, !"""

    def test_bare_option(self):
        self.env.config['JINJA2_CONTEXT'] = {'name': 'Randall'}
        self.create_files({'in': """Hi there, {{ name }}!"""})
        self.mkbundle('in', filters='jinja2', output='out.template').build()
        assert self.get('out.template') == """Hi there, Randall!"""


class TestClosure(TempEnvironmentHelper):

    default_files = {
        'foo.js': u"""
        // Cômment wíth sóme Ünicòde
        function foo(bar) {
            var dummy;
            document.write ( bar ); /* Write */
        }
        """
    }

    def setup(self):
        try:
            import closure
        except ImportError:
            raise SkipTest()

        TempEnvironmentHelper.setup(self)

    def test_closure(self):
        self.mkbundle('foo.js', filters='closure_js', output='out.js').build()
        assert self.get('out.js') == 'function foo(bar){var dummy;document.write(bar)};\n'

    def test_optimization(self):
        self.env.config['CLOSURE_COMPRESSOR_OPTIMIZATION'] = 'SIMPLE_OPTIMIZATIONS'
        self.mkbundle('foo.js', filters='closure_js', output='out.js').build()
        assert self.get('out.js') == 'function foo(a){document.write(a)};\n'

    def test_extra_args(self):
        self.env.config['CLOSURE_EXTRA_ARGS'] = ['--output_wrapper', 'hello: %output%']
        self.mkbundle('foo.js', filters='closure_js', output='out.js').build()
        assert self.get('out.js') == 'hello: function foo(bar){var dummy;document.write(bar)};\n'


class TestCssRewrite(TempEnvironmentHelper):

    def test(self):
        self.create_files({'in.css': '''h1 { background: url(sub/icon.png) }'''})
        self.create_directories('g')
        self.mkbundle('in.css', filters='cssrewrite', output='g/out.css').build()
        assert self.get('g/out.css') == '''h1 { background: url(../sub/icon.png) }'''

    def test_change_folder(self):
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

    def test_hostnames(self):
        """[Regression] Properly deal with full urls.
        """
        self.env.append_path(self.path('g'), 'http://input.com/')
        self.env.url = 'http://output.com/'

        self.create_directories('g')
        self.create_files({'g/in.css': '''h1 { background: url(sub/icon.png) }'''})

        self.mkbundle('in.css', filters='cssrewrite', output='out.css').build()
        self.p('out.css')
        assert self.get('out.css') == '''h1 { background: url(http://input.com/sub/icon.png) }'''

    def test_replace_with_cache(self):
        """[Regression] Test replace mode while cache is active.

        This used to fail due to an unhashable key being returned by
        the filter."""
        cssrewrite = get_filter('cssrewrite', replace={'old/': 'new/'})
        self.env.cache = True
        self.create_files({'in.css': '''h1 { background: url(old/sub/icon.png) }'''})
        # Does not raise an exception.
        self.mkbundle('in.css', filters=cssrewrite, output='out.css').build()
        assert self.get('out.css') == '''h1 { background: url(new/sub/icon.png) }'''

    def test_replacement_lambda(self):
        self.create_files({'in.css': '''h1 { background: url(old/sub/icon.png) }'''})
        cssrewrite = get_filter('cssrewrite', replace=lambda url: re.sub(r'^/?old/', '/new/', url))
        self.mkbundle('in.css', filters=cssrewrite, output='out.css').build()
        assert self.get('out.css') == '''h1 { background: url(/new/sub/icon.png) }'''

    def test_not_touching_data_uri(self):
        """Data uris are left alone."""
        # For this bug to trigger, env.url needs to have a directory part
        self.env.url = '/sub/dir'
        self.create_files({'in.css': '''h1 {
            background-image: url(data:image/png;base64,iVBORw0KGgoA);
        }'''})
        self.mkbundle('in.css', filters='cssrewrite', output='out.css').build()
        assert self.get('out.css') == '''h1 {
            background-image: url(data:image/png;base64,iVBORw0KGgoA);
        }'''


class TestDataUri(TempEnvironmentHelper):

    default_files = {
        'in.css': '''h1 { background: url(sub/icon.png) }'''
    }

    def test(self):
        self.create_files({'sub/icon.png': 'foo'})
        self.mkbundle('in.css', filters='datauri', output='out.css').build()
        assert self.get('out.css') == 'h1 { background: url(data:image/png;base64,Zm9v) }'

    def test_missing_file(self):
        """No error is raised if a file is missing."""
        self.mkbundle('in.css', filters='datauri', output='out.css').build()
        assert self.get('out.css') == 'h1 { background: url(sub/icon.png) }'

    def test_max_size(self):
        self.env.config['datauri_max_size'] = 2
        self.create_files({'sub/icon.png': 'foo'})
        self.mkbundle('in.css', filters='datauri', output='out.css').build()
        assert self.get('out.css') == 'h1 { background: url(sub/icon.png) }'


class TestLess(TempEnvironmentHelper):

    default_files = {
        'foo.less': "h1 { color: #FFFFFF; }",
    }

    def setup(self):
        if not find_executable('lessc'):
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test(self):
        self.mkbundle('foo.less', filters='less', output='out.css').build()
        assert self.get('out.css') == 'h1 {\n  color: #FFFFFF;\n}\n'

    def test_import(self):
        """Test referencing other files."""
        # Note that apparently less can only import files that generate no
        # output, i.e. mixins, variables etc.
        self.create_files({
            'import.less': '''
               @import "foo.less";
               span { color: @c }
               ''',
            'foo.less': '@c: red;'})
        self.mkbundle('import.less', filters='less', output='out.css').build()
        assert self.get('out.css') == 'span {\n  color: red;\n}\n'

    def test_run_in_debug_mode(self):
        """A setting can be used to make less not run in debug."""
        self.env.debug = True
        self.env.config['less_run_in_debug'] = False
        self.mkbundle('foo.less', filters='less', output='out.css').build()
        assert self.get('out.css') == self.default_files['foo.less']

    def test_include_path(self):
        '''It should allow specifying extra include paths'''
        self.create_files({
            'import.less': '''
               @import "extra.less";
               span { color: @c }
               ''',
            'extra/path/extra.less': '@c: red;'})
        self.env.config['less_paths'] = ['extra/path']
        self.mkbundle('import.less', filters='less', output='out.css').build()
        assert self.get('out.css') == 'span {\n  color: red;\n}\n'

    def test_include_path_order(self):
        '''It should preserve extra include paths order'''
        self.create_files({
            'import.less': '''
               @import "extra.less";
               span { color: @c }
               ''',
            'extra/path/extra.less': '@c: red;',
            'other/path/extra.less': '@c: blue;'})
        self.env.config['less_paths'] = ['extra/path', 'other/path']
        self.mkbundle('import.less', filters='less', output='out.css').build()
        assert self.get('out.css') == 'span {\n  color: red;\n}\n'

    def test_as_output_filter(self):
        """The less filter can be configured to work as on output filter,
        first merging the sources together, then applying less.
        """
        # To test this, split a sass rules into two files.
        less_output = get_filter('less', as_output=True)
        self.create_files(
            {'p1': '@base: #123456;', 'p2': 'P { color: @base }'}
        )
        self.mkbundle(
            'p1', 'p2', filters=less_output, output='out.css'
        ).build()
        assert self.get('out.css') == """P {\n  color: #123456;\n}\n"""

        less_output = get_filter('less', as_output=False)
        self.create_files(
            {'p1': '@base: #123456;', 'p2': 'P { color: @base }'}
        )

        def mkbundle():
            self.mkbundle(
                'p1', 'p2', filters=less_output, output='out2.css'
            ).build()

        assert_raises(FilterError, mkbundle)


class TestSass(TempEnvironmentHelper):

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

    def setup(self):
        if not find_executable('sass'):
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test_sass(self):
        sass = get_filter('sass', debug_info=False)
        self.mkbundle('foo.sass', filters=sass, output='out.css').build()
        assert self.get('out.css') in (
            # Sass <= 3.3
            """/* line 1 */\nh1 {\n  font-family: "Verdana";\n  color: white;\n}\n""",
            # Sass 3.4+
            """/* line 1 */\nh1 {\n  font-family: "Verdana";\n  color: #FFFFFF;\n}\n""",
        )

    def test_sass_import(self):
        """Test referencing other files in sass.
        """
        sass = get_filter('sass', debug_info=False)
        self.create_files({'import-test.sass': '''@import foo.sass'''})
        self.mkbundle('import-test.sass', filters=sass, output='out.css').build()
        assert (
            # Sass <= 3.3
            doctest_match("""/* line 1, ...foo.sass */\nh1 {\n  font-family: "Verdana";\n  color: white;\n}\n""", self.get('out.css'))
            # Sass 3.4+
            or doctest_match("""/* line 1, ...foo.sass */\nh1 {\n  font-family: "Verdana";\n  color: #FFFFFF;\n}\n""", self.get('out.css'))
        )

    def test_scss(self):
        # SCSS is a CSS superset, should be able to compile the CSS file just fine
        scss = get_filter('scss', debug_info=False)
        self.mkbundle('foo.css', filters=scss, output='out.css').build()
        assert self.get('out.css') == """/* line 2 */\nh1 {\n  font-family: "Verdana";\n  color: #FFFFFF;\n}\n"""

    def test_debug_info_option(self):
        # The debug_info argument to the sass filter can be configured via
        # a global SASS_DEBUG_INFO option.
        self.env.config['SASS_DEBUG_INFO'] = False
        self.mkbundle('foo.sass', filters=get_filter('sass'), output='out.css').build(force=True)
        assert not '-sass-debug-info' in self.get('out.css')

        # However, an instance-specific debug_info option takes precedence.
        self.mkbundle('foo.sass', filters=get_filter('sass', debug_info=True), output='out.css').build(force=True)
        assert '-sass-debug-info' in self.get('out.css')

        # If the value is None (the default), then the filter will look
        # at the global debug setting to determine whether to include debug
        # info. Note: It looks at environment.debug! The local bundle.debug
        # is likely to be always False for Sass, so is of little help.
        self.env.config['SASS_DEBUG_INFO'] = None
        self.env.debug = True
        self.mkbundle('foo.sass', filters=get_filter('sass'),
                      output='out.css', debug=False).build(force=True)
        assert '-sass-debug-info' in self.get('out.css')
        self.env.debug = False
        self.mkbundle('foo.sass', filters=get_filter('sass'),
                      output='out.css').build(force=True)
        assert not '-sass-debug-info' in self.get('out.css')

    def test_as_output_filter(self):
        """The sass filter can be configured to work as on output filter,
        first merging the sources together, then applying sass.
        """
        # To test this, split a sass rules into two files.
        sass_output = get_filter('sass', debug_info=False, as_output=True)
        self.create_files({'p1': 'h1', 'p2': '\n  color: #FFFFFF'})
        self.mkbundle('p1', 'p2', filters=sass_output, output='out.css').build()
        assert self.get('out.css') in (
            # Sass <= 3.3
            """/* line 1 */\nh1 {\n  color: white;\n}\n""",
            # Sass 3.4+
            """/* line 1 */\nh1 {\n  color: #FFFFFF;\n}\n""",
        )

    def test_custom_include_path(self):
        """Test a custom include_path.
        """
        sass_output = get_filter('sass', debug_info=False, as_output=True,
                                 load_paths=['includes'])
        self.create_files({
            'includes/vars.sass': '$a_color: #FFFFFF',
            'base.sass': '@import vars.sass\nh1\n  color: $a_color'})
        self.mkbundle('base.sass', filters=sass_output, output='out.css').build()
        assert self.get('out.css') in (
            # Sass <= 3.3
            """/* line 2 */\nh1 {\n  color: white;\n}\n""",
            # Sass 3.4+
            """/* line 2 */\nh1 {\n  color: #FFFFFF;\n}\n""",
        )


class TestPyScss(TempEnvironmentHelper):

    default_files = {
        'foo.scss': """@import "bar"; a {color: red + green; }""",
        'bar.scss': 'h1{color:red}'
    }

    def setup(self):
        try:
            import scss
            self.scss = scss
        except ImportError:
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test(self):
        self.mkbundle('foo.scss', filters='pyscss', output='out.css').build()
        assert self.get('out.css') == 'h1 {\n  color: #ff0000;\n}\na {\n  color: #ff8000;\n}\n'

    def test_assets(self):
        try:
            import PIL
            # Travis does not support PNG files, see
            # https://github.com/travis-ci/travis-ci/issues/746
            from PIL import Image
            Image.new('RGB', (10,10)).save(StringIO(), 'png')
        except (ImportError, IOError):
            raise SkipTest()
        self.create_files({'noise.scss': 'h1 {background: background-noise()}'})
        self.mkbundle('noise.scss', filters='pyscss', output='out.css').build()

        assert doctest_match(
            'h1 {\n  background: url("...png");\n}\n',
            self.get('out.css'),)


class TestLibSass(TempEnvironmentHelper):
    default_files = {
        'foo.scss': '@import "bar"; a {color: red + green; }',
        'bar.scss': 'h1{color:red}',
        'a.scss': '$foo: bar;',
        'b.scss': '$foo: foo !default; .test {background-color: $foo;}'
    }

    def setup(self):
        try:
            import sass
            self.sass = sass
        except ImportError:
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test(self):
        self.mkbundle('foo.scss', filters='libsass', output='out.css').build()
        assert self.get('out.css') == (
            'h1 {\n  color: red; }\n\na {\n  color: #ff8000; }\n'
        )

    def test_compressed(self):
        libsass = get_filter('libsass', style='compressed')
        self.mkbundle('foo.scss', filters=libsass, output='out.css').build()
        assert self.get('out.css') == 'h1{color:red}a{color:#ff8000}\n'

    def test_as_output_filter(self):
        libsass = get_filter('libsass', as_output=True)
        self.mkbundle('a.scss', 'b.scss', filters=libsass, output='out.css').build()
        assert self.get('out.css') == (
            '.test {\n  background-color: bar; }\n'
        )

    def test_as_input_filter(self):
        libsass = get_filter('libsass', as_output=False)
        self.mkbundle('a.scss', 'b.scss', filters=libsass, output='out.css').build()
        assert self.get('out.css') == (
            '\n.test {\n  background-color: foo; }\n'
        )

    def test_as_output_filter_compressed(self):
        libsass = get_filter('libsass', as_output=True, style='compressed')
        self.mkbundle('a.scss', 'b.scss', filters=libsass, output='out.css').build()
        assert self.get('out.css') == '.test{background-color:bar}\n'


class TestCompass(TempEnvironmentHelper):

    default_files = {
        'foo.scss': u"""
            h1  {
                font-family: "Verdana"  ;
                color: #FFFFFF;
            }
        """,
        'unicode.scss': u"""
            h1 {
                content: "áé";
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

    def setup(self):
        if not find_executable('compass'):
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test_compass(self):
        self.mkbundle('foo.sass', filters='compass', output='out.css').build()
        assert doctest_match("""/* ... */\nh1 {\n  font-family: "Verdana";\n  color: white;\n}\n""", self.get('out.css'))

    def test_compass_with_imports(self):
        self.mkbundle('import.scss', filters='compass', output='out.css').build()
        assert doctest_match("""/* ... */\nh1 {\n  font-family: "Verdana";\n  color: #FFFFFF;\n}\n""", self.get('out.css'))

    def test_compass_with_scss(self):
        # [bug] test compass with scss files
        self.mkbundle('foo.scss', filters='compass', output='out.css').build()
        assert doctest_match("""/* ... */\nh1 {\n  font-family: "Verdana";\n  color: #FFFFFF;\n}\n""", self.get('out.css'))

    def test_compass_with_unicode(self):
        # [bug] test compass with scss files
        self.mkbundle('unicode.scss', filters='compass', output='out.css').build()

        # It's very hard to test this with doctest_match
        # And by asserting that it's in the content this test is proven
        from webassets.six import PY3
        if PY3:
            assert """content: "áé";""" in self.get('out.css')
        else:
            assert """content: "\xc3\xa1\xc3\xa9";""" in self.get('out.css')

    def test_images_dir(self):
        # [bug] Make sure the compass plugin can reference images. It expects
        # paths to be relative to env.directory.
        self.create_files({'datauri.scss': 'h1 { background: inline-image("test.png") }', 'test.png': 'foo'})
        self.mkbundle('datauri.scss', filters='compass', output='out.css').build()
        assert doctest_match("""/* ... */\nh1 {\n  background: url('data:image/png;base64,Zm9v');\n}\n""", self.get('out.css'))

    def test_images_url(self):
        # [bug] Make sure the compass plugin outputs the correct urls to images
        # when using the image-url helper.
        self.env.url = 'http://assets.host.com/the-images'
        self.create_files({'imguri.scss': 'h1 { background: image-url("test.png") }'})
        self.mkbundle('imguri.scss', filters='compass', output='out.css').build()
        assert doctest_match("""/* ... */\nh1 {\n  background: url('http://assets.host.com/the-images/test.png');\n}\n""", self.get('out.css'))


class TestCompassConfig(object):

    config = {
        'http_path': '/',
        'relative_assets': True,
        'output_style': ':nested',
        'javascripts_dir': u'diretório_javascript',
        'sprite_load_path': [
            'static/img',
        ],
        'additional_import_paths': (
            'static/sass',
        ),
        'sass_options': {
            'k': 'v'
        }
    }

    def setup(self):
        self.compass_config = CompassConfig(self.config).to_string()

    def test_compass_config_is_unicode(self):
        from webassets.six import text_type
        assert isinstance(self.compass_config, text_type)

    def test_string_value(self):
        assert "http_path = '/'" in self.compass_config

    def test_boolean_value(self):
        assert "relative_assets = true" in self.compass_config

    def test_symbol_value(self):
        assert 'output_style = :nested' in self.compass_config

    def test_list_value(self):
        assert "sprite_load_path = ['static/img']" in self.compass_config

    def test_tuple_value(self):
        assert "additional_import_paths = ['static/sass']" in self.compass_config

    def test_dict_value(self):
        assert "sass_options = {'k' => 'v'}" in self.compass_config

class TestJST(TempEnvironmentHelper):

    default_files = {
        'templates/foo.jst': "<div>Im a normal .jst template.</div>",
        'templates/bar.html': "<div>Im an html jst template.  Go syntax highlighting!</div>"
    }

    def setup(self):
        TempEnvironmentHelper.setup(self)

    def test_jst(self):
        self.mkbundle('templates/*', filters='jst', output='out.js').build()
        contents = self.get('out.js')
        assert 'Im a normal .jst template' in contents
        assert 'Im an html jst template.  Go syntax highlighting!' in contents

    def test_compiler_config(self):
        self.env.config['JST_COMPILER'] = '_.template'
        self.mkbundle('templates/*', filters='jst', output='out.js').build()
        assert '_.template' in self.get('out.js')
        # make sure the default builder is not included
        assert "var template =" not in self.get('out.js')

    def test_compiler_is_false(self):
        """Output strings directly if template_function == False."""
        self.env.config['JST_COMPILER'] = False
        self.mkbundle('templates/*.jst', filters='jst', output='out.js').build()
        assert "JST['foo'] = \"" in self.get('out.js')
        assert "var template =" not in self.get('out.js')

    def test_compiler_is_none(self):
        """Make sure the default builder is included
        if compiler is not specified """
        self.mkbundle('templates/*.jst', filters='jst', output='out.js').build()
        assert "var template =" in self.get('out.js')

    def test_namespace_config(self):
        self.env.config['JST_NAMESPACE'] = 'window.Templates'
        self.mkbundle('templates/*', filters='jst', output='out.js').build()
        assert 'window.Templates' in self.get('out.js')

    def test_nested_naming(self):
        self.create_files({'templates/foo/bar/baz.jst': """<span>In your foo bars.</span>"""})
        self.mkbundle('templates/foo/bar/*', 'templates/bar.html', filters='jst', output='out.js').build()
        assert '\'foo/bar/baz\'' in self.get('out.js')

    def test_single_template(self):
        """Template name is properly determined if there is only a single file."""
        self.create_files({'baz.jst': """<span>Baz?</span>"""})
        self.mkbundle('*.jst', filters='jst', output='out.js').build()
        assert '\'baz\'' in self.get('out.js')

    def test_repeated_calls(self):
        """[Regression] Does not break if used multiple times."""
        self.create_files({'baz.jst': """<span>Baz?</span>"""})
        bundle = self.mkbundle('*.jst', filters='jst', output='out.js')\

        bundle.build(force=True)
        first_output = self.get('out.js')
        assert '\'baz\'' in first_output

        bundle.build(force=True)
        assert self.get('out.js') == first_output

    def test_option_bare(self):
        """[Regression] Test the JST_BARE option can be set to False.
        """
        self.create_files({'baz.jst': """<span>Baz?</span>"""})
        b = self.mkbundle('*.jst', filters='jst', output='out.js')

        # The default is bare==True (i.e. no closure)
        b.build(force=True)
        assert not self.get('out.js').startswith('(function()')
        assert not self.get('out.js').endswith('})();')

        # If set to False, the closure is added.
        self.env.config['JST_BARE'] = False
        self.mkbundle('*.jst', filters='jst', output='out.js').build(force=True)
        assert self.get('out.js').startswith('(function()')
        assert self.get('out.js').endswith('})();')

    def test_cache(self):
        """[Regression] Test that jst filter does not break the caching.
        """
        # Enable use of cache
        self.env.cache = True

        self.create_files({'baz.jst': """old value"""})
        bundle = self.mkbundle('*.jst', filters='jst', output='out.js')
        bundle.build()

        # Change the file
        self.create_files({'baz.jst': """new value"""})

        # Rebuild with force=True, so it's not a question of the updater
        # not doing its job.
        bundle.build(force=True)

        assert 'new value' in self.get('out.js')

    def test_backslashes_escaped(self):
        """Test that JavaScript string literals are correctly escaped.
        """
        self.create_files({'backslashes.jst': """<input type="text" pattern="\S*"/>"""})
        self.mkbundle('*.jst', filters='jst', output='out.js').build()
        assert r"""template("<input type=\"text\" pattern=\"\\S*\"/>")""" in self.get('out.js')

    def test_backslashes_changed_to_slash_in_name(self):
        # Using normpath() here so that the filenames will only have
        # backslashes on Windows.
        self.create_files({
            os.path.normpath('templates/foo/test.jst'): '<div>Test</div>',
            os.path.normpath('templates/bar/other.jst'): '<div>Other</div>'})
        self.mkbundle('templates/*/*.jst', filters='jst', output='out.js').build()
        assert "'foo/test'" in self.get('out.js')
        assert "'bar/other'" in self.get('out.js')

    def test_separator_config(self):
        self.env.config['JST_DIR_SEPARATOR'] = '_'
        self.create_files({
            'templates/foo/test.jst': '<div>Test</div>',
            'templates/bar/other.jst': '<div>Other</div>'})
        self.mkbundle('templates/*/*.jst', filters='jst', output='out.js').build()
        assert "'foo_test'" in self.get('out.js')
        assert "'bar_other'" in self.get('out.js')

class TestHandlebars(TempEnvironmentHelper):

    default_files = {
        'foo.html': """
            <div class="foo">foo</div>
            """,
        'dir/bar.html': """
            <div class="bar">bar</div>
            """
    }

    def setup(self):
        if not find_executable('handlebars'):
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test_basic(self):
        self.mkbundle('foo.html', 'dir/bar.html',
                      filters='handlebars', output='out.js').build()
        assert 'Handlebars' in self.get('out.js')
        assert "'foo.html'" in self.get('out.js')
        assert "'dir/bar.html'" in self.get('out.js')

    def test_custom_root(self):
        self.env.config['handlebars_root'] = 'dir'
        self.mkbundle('dir/bar.html', filters='handlebars', output='out.js').build()
        assert "'bar.html'" in self.get('out.js')

    def test_auto_root(self):
        self.mkbundle('dir/bar.html', filters='handlebars', output='out.js').build()
        assert "'bar.html'" in self.get('out.js')


class TestJinja2JS(TempEnvironmentHelper):

    default_files = {
        'foo.soy': (
            "{namespace examples.simple}\n"
            "\n"
            "/**\n"
            " * Says hello to the world.\n"
            " */\n"
            "{template .helloWorld}\n"
            "  Hello world!\n"
            "{/template}\n"
        )
    }

    def setup(self):
        try:
            import closure_soy
        except:
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test(self):
        self.mkbundle('foo.soy', filters='closure_tmpl', output='out.js').build()
        assert self.get("out.js") == (
            "// This file was automatically generated from foo.soy."
            + "\n// Please don't edit this file by hand."
            + "\n"
            + "\nif (typeof examples == 'undefined') { var examples = {}; }"
            + "\nif (typeof examples.simple == 'undefined') { examples.simple = {}; }"
            + "\n"
            + "\n"
            + "\nexamples.simple.helloWorld = function(opt_data, opt_ignored) {"
            + "\n  return 'Hello world!';"
            + "\n};"
            + "\n")


class TestTypeScript(TempEnvironmentHelper):

    default_files = {
        'foo.ts': """class X { z: number; }"""
    }

    def setup(self):
        if not find_executable('tsc'):
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test(self):
        self.mkbundle('foo.ts', filters='typescript', output='out.js').build()
        assert self.get("out.js") in [
            # older versions of typescript
            'var X = (function () {\n    function X() {\n    }\n    return X;\n})();\n',
            # newer versions
            'var X = (function () {\n    function X() {\n    }\n    return X;\n}());\n'
        ]


class TestRequireJS(TempEnvironmentHelper):

    default_files = {
        'requirejs.json': '{baseUrl: "/static/"}',
        'script/app.js': '''\
define(['./utils'], function(util) {
  util.debug('APP');
});
''',
        'script/utils.js': '''\
define(function() {
  return {debug: console.log};
});
''',
    }

    compiled_output = '''\
define("script/utils",[],function(){return{debug:console.log}}),\
define("script/app",["./utils"],function(e){e.debug("APP")});\
'''

    def setup(self):
        if not find_executable('r.js'):
            raise SkipTest('"r.js" executable not found')
        TempEnvironmentHelper.setup(self)
        self.env.config['requirejs_config'] = self.path('requirejs.json')
        self.env.config['requirejs_baseUrl'] = self.path('')

    def test_build(self):
        self.mkbundle('script/app.js', filters='requirejs', output='out.js').build()
        assert self.get('out.js') == self.compiled_output

    def test_build_nooptimize(self):
        self.env.config['requirejs_optimize'] = 'none'
        self.mkbundle('script/app.js', filters='requirejs', output='out.js').build()
        assert self.get('out.js').strip() == '''
define('script/utils',[],function() {
  return {debug: console.log};
});

define('script/app',['./utils'], function(util) {
  util.debug('APP');
});
'''.strip()

    def test_build_debug_rid(self):
        self.env.debug = True
        self.env.config['requirejs_run_in_debug'] = True
        self.mkbundle('script/app.js', filters='requirejs', output='out.js').build()
        assert self.get('out.js') == self.compiled_output

    def test_build_debug_norid(self):
        self.env.debug = True
        self.env.config['requirejs_run_in_debug'] = False
        self.mkbundle('script/app.js', filters='requirejs', output='out.js').build()
        assert self.get('out.js') == '''\
define(['./utils'], function(util) {
  util.debug('APP');
});
'''


class TestClosureStylesheets(TempEnvironmentHelper):

    default_files = {
        'test.css': """
        @def COLOR red;
        p {
            color: COLOR;
        }
        """
    }

    def setup(self):
        if not 'CLOSURE_STYLESHEETS_PATH' in os.environ:
            raise SkipTest()
        TempEnvironmentHelper.setup(self)

    def test_compiler(self):
        self.mkbundle('test.css', filters = 'closure_stylesheets_compiler', output = 'output.css').build()
        assert 'color: red' in self.get('output.css')

    def test_minifier(self):
        self.mkbundle('test.css', filters = 'closure_stylesheets_minifier', output = 'output.css').build()
        assert self.get('output.css') == 'p{color:red}'


class TestAutoprefixer6Filter(TempEnvironmentHelper):
    default_files = {
        'test.css': """
        .shadow {
            animation: blablabla
        }
        """
    }

    def test_first(self):
        self.mkbundle('test.css', filters='autoprefixer6', output='output.css').build()
        out = self.get('output.css')
        assert 'webkit' in out


class TestBabel(TempEnvironmentHelper):
    default_files = {
        'test.es6': """var x = (p) => { return false; };"""
    }

    def test_es2015(self):
        es2015 = get_filter('babel', presets='es2015')
        try:
            self.mkbundle('test.es6', filters=es2015, output='output.js').build()
        except FilterError as e:
            # babel is not installed, that's ok.
            if 'Program file not found' in e.message:
                raise SkipTest()
            else:
                raise
        assert "var x = function x" in self.get('output.js')

    def test_extra_args(self):
        self.env.config['BABEL_EXTRA_ARGS'] = ['--minified']
        self.mkbundle('test.es6', filters='babel', output='output.js').build()
        assert (self.get('output.js').strip() ==
                'var x=p => {return false};')

    def test_run_in_debug_mode(self):
        """A setting can be used to make babel not run in debug."""
        self.env.debug = True
        self.env.config['babel_run_in_debug'] = False
        self.mkbundle('test.es6', filters='babel', output='output.js').build()
        assert self.get('output.js') == self.default_files['test.es6']

