from __future__ import with_statement
import sys
from nose.tools import assert_raises, assert_true
import textwrap
from webassets.env import Environment
from webassets.filter import Filter, get_filter
from webassets.utils import StringIO
from webassets.bundle import Bundle
from webassets.loaders import PythonLoader, YAMLLoader, LoaderError
from webassets.exceptions import EnvironmentError
from nose import SkipTest


class TestYAML(object):

    def setup(self):
        try:
            import yaml
        except ImportError:
            raise SkipTest()

    def loader(self, text, filename=None):
        io = StringIO(textwrap.dedent(text))
        if filename:
            io.name = filename
        return YAMLLoader(io)

    def test_load_bundles(self):
        bundles = self.loader("""
        standard:
            filters: cssmin,jsmin
            output: output.css
            contents:
                - file1
                - file2
        empty-bundle:
        single-content-as-string-bundle:
            contents: only-this
        nested:
            output: nested.css
            filters: cssmin
            contents:
                - cssfile1
                - filters: less
                  contents:
                    - lessfile1
                    - lessfile2
                    - contents:
                        reallynested.css
                      config:
                        closure_bin: /tmp/closure
                    - lessfile3
                
        """).load_bundles()
        assert len(bundles) == 4
        assert bundles['standard'].output == 'output.css'
        assert len(bundles['standard'].filters) == 2
        assert bundles['standard'].contents == ('file1', 'file2')
        assert bundles['empty-bundle'].contents == ()
        assert bundles['single-content-as-string-bundle'].contents == ('only-this',)
        assert bundles['nested'].output == 'nested.css'
        assert len(bundles['nested'].filters) == 1
        assert len(bundles['nested'].contents) == 2
        nested_bundle = bundles['nested'].contents[1]
        assert isinstance(nested_bundle, Bundle)
        assert len(nested_bundle.filters) == 1
        assert len(nested_bundle.contents) == 4
        assert isinstance(nested_bundle.contents[2], Bundle)
        assert nested_bundle.contents[2].config['closure_bin'] == '/tmp/closure'

    def test_load_recursive_bundles(self):
        bundles = self.loader("""
        standard:
            filters: cssmin,jsmin
            output: output.css
            contents:
                - file1
                - file2
        recursive:
            output: recursive.css
            filters: jsmin
            contents:
                - cssfile1
                - standard
                - cssfile2
        """).load_bundles()
        assert len(bundles) == 2
        assert bundles['recursive'].contents[1].contents == bundles['standard'].contents
        assert isinstance(bundles['recursive'].contents[1], Bundle)

    def test_empty_files(self):
        """YAML loader can deal with empty files.
        """
        self.loader("""""").load_bundles()
        self.loader("""""").load_environment()

    def test_load_environment(self):
        environment = self.loader("""
        url: /foo
        directory: something
        versions: 'timestamp'
        auto_build: true
        url_expire: true
        config:
            compass_bin: /opt/compass

        bundles:
            test:
                output: foo
        """).load_environment()
        assert environment.url == '/foo'
        assert environment.url_expire == True
        assert environment.auto_build == True
        assert environment.config['versions'] == 'timestamp'
        assert environment.config['COMPASS_BIN'] == '/opt/compass'

        # Because the loader isn't aware of the file location, the
        # directory is read as-is, relative to cwd rather than the
        # file location.
        assert environment.config['directory'] == 'something'

        # [bug] Make sure the bundles are loaded as well.
        assert len(environment) == 1

    def test_load_environment_no_url_or_directory(self):
        """Check that "url" and "directory" are not required.
        """
        self.loader("""foo: bar""").load_environment()

    def test_load_environment_directory_base(self):
        environment = self.loader("""
        url: /foo
        directory: ../something
        """, filename='/var/www/project/config/yaml').load_environment()
        # The directory is considered relative to the YAML file location.
        assert environment.directory == '/var/www/project/something'

    def test_load_extra_default(self):
        """[Regression] If no extra= is given, the value defaults to {}"""
        bundles = self.loader("""
        foo:
           output: foo
        """).load_bundles()
        assert bundles['foo'].extra == {}


class TestPython(object):
    """Test the PythonLoader.
    """

    def test_path(self):
        """[bug] Regression test: Python loader does not leave
        sys.path messed up.
        """
        old_path = sys.path[:]
        loader = PythonLoader('sys')
        assert sys.path == old_path

    def test_load_bundles(self):
        import types
        module = types.ModuleType('test')
        module.foo = Bundle('bar')

        loader = PythonLoader(module)
        bundles = loader.load_bundles()
        assert len(bundles) == 1
        assert list(bundles.values())[0].contents[0] == 'bar'

    def test_load_environment_with_prefix(self):
        import types
        module = types.ModuleType("testing")
        module2 = types.ModuleType("testing2")
        module.environment = Environment() # default name
        module2.assets = Environment()
        sys.modules["testing"] = module
        sys.modules["testing2"] = module2

        loader = PythonLoader("testing")
        env = loader.load_environment()
        assert env == module.environment

        loader2 = PythonLoader("testing:environment")
        assert loader2.environment == "environment"
        env2 = loader2.load_environment()
        assert env2 == module.environment

        loader3 = PythonLoader("testing2:assets")
        assert loader3.environment == "assets"
        env3 = loader3.load_environment()
        assert env3 == module2.assets

class TestYAMLCustomFilters(TestYAML):

    def setup(self):
        super(TestYAMLCustomFilters, self).setup()

        # If zope.dottedname is not installed, that's OK
        try:
            import zope.dottedname.resolve
        except ImportError:
            raise SkipTest()
        # Save off the original get_import_resolver
        self.original_resolver = YAMLLoader._get_import_resolver
        # Make a mock
        def mock(cls):
            raise ImportError
        self.mock_resolver = mock

    def mock_importer(self):
        """ Mock the import resolver to a fake one that raises import error.
        Be sure to call reset_importer if you use this at the beginning of
        any test."""
        YAMLLoader._get_import_resolver = self.mock_resolver

    def reset_importer(self):
        """ Reset the import resolver to the default one """
        YAMLLoader._get_import_resolver = self.original_resolver

    def test_cant_import_zope_is_fine(self):
        """ Check that a YAML file without filters is fine if the import of
        zope.dottedname fails """
        self.mock_importer()
        self.loader("""foo: bar""").load_environment()
        self.reset_importer()

    def test_need_zope_to_have_filter(self):
        """ Check that we get an error if the zope.dottedname module is not
        installed and they try to use custom filters """
        self.mock_importer()
        loader =  self.loader("""
        filters:
            - webassets.filter.less.Less
        """)
        assert_raises(EnvironmentError, loader.load_environment)
        self.reset_importer()

    def test_load_filter_module_throws_exc(self):
        """ Check that passing dotted module path throws an exception """
        # Try to load based on module name, instead of the class
        loader =  self.loader("""
        filters:
            - webassets.filter.less
        """)
        assert_raises(LoaderError, loader.load_environment)

    def test_bad_filter_throws_exc(self):
        """ Test that importing filters that don't exist throws an exception """
        loader =  self.loader("""
        filters:
            - webassets.fake.filter
        """)
        assert_raises(LoaderError, loader.load_environment)

    def test_load_filters(self):
        """Check that filters can be loaded from YAML """
        # Delete the less filter
        import webassets.filter
        del webassets.filter._FILTERS['less']
        # Verify that it was deleted
        assert_raises(ValueError, get_filter, 'less')
        # Load it again from YAML
        self.loader("""
        filters:
            - webassets.filter.less.Less
        """).load_environment()
        # Check that it's back
        assert_true(isinstance(get_filter('less'), Filter))
