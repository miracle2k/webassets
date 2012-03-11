from __future__ import with_statement
import sys
from nose.tools import assert_raises
import textwrap
from StringIO import StringIO
from webassets.bundle import Bundle
from webassets.loaders import PythonLoader, YAMLLoader, LoaderError
from webassets.exceptions import ImminentDeprecationWarning
from nose import SkipTest
from helpers import check_warnings


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
            filters: cssmin,gzip
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

    def test_load_recursive_bundles(self):
        bundles = self.loader("""
        standard:
            filters: cssmin,gzip
            output: output.css
            contents:
                - file1
                - file2
        recursive:
            output: recursive.css
            filters: cssmin
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
        # A LoaderError is what we expect here, rather than, say, a TypeError.
        assert_raises(LoaderError, self.loader("""""").load_environment)

    def test_load_environment_error(self):
        """Check that "url" and "directory" are required.
        """
        assert_raises(LoaderError, self.loader("""
        url: /foo
        """).load_environment)
        assert_raises(LoaderError, self.loader("""
        directory: bar
        """).load_environment)

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
        assert environment.directory == 'something'

        # [bug] Make sure the bundles are loaded as well.
        assert len(environment) == 1

    def test_load_deprecated_attrs(self):
        with check_warnings(("", ImminentDeprecationWarning)) as w:
            environment = self.loader("""
            url: /foo
            directory: something
            updater: false
            """).load_environment()
            assert environment.auto_build == False

    def test_load_environment_directory_base(self):
        environment = self.loader("""
        url: /foo
        directory: ../something
        """, filename='/var/www/project/config/yaml').load_environment()
        # The directory is considered relative to the YAML file location.
        assert environment.directory == '/var/www/project/something'


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
        assert bundles.values()[0].contents[0] == 'bar'

