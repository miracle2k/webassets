from __future__ import with_statement

from nose import SkipTest
from nose.tools import assert_raises

from django.conf import settings
from django.template import Template, Context
from django_assets.loaders import DjangoLoader
from django_assets import Bundle, register as django_env_register
from django_assets.env import get_env, reset as django_env_reset
from tests.helpers import (
    TempDirHelper,
    TempEnvironmentHelper as BaseTempEnvironmentHelper, assert_raises_regexp)
from webassets.filter import get_filter
from webassets.exceptions import BundleError, ImminentDeprecationWarning

from tests.helpers import check_warnings

try:
    from django.templatetags.assets import AssetsNode
except ImportError:
    # Since #12295, Django no longer maps the tags.
    from django_assets.templatetags.assets import AssetsNode


class TempEnvironmentHelper(BaseTempEnvironmentHelper):
    """Base-class for tests which will:

    - Reset the Django settings after each test.
    - Reset the django-assets environment after each test.
    - Initialize MEDIA_ROOT to point to a temporary directory.
    """

    def setup(self):
        TempDirHelper.setup(self)

        # Reset the webassets environment.
        django_env_reset()
        self.env = get_env()

        # Use a temporary directory as MEDIA_ROOT
        settings.MEDIA_ROOT = self.create_directories('media')[0]

        # Some other settings without which we are likely to run
        # into errors being raised as part of validation.
        setattr(settings, 'DATABASES', {})
        settings.DATABASES['default'] = {'ENGINE': ''}

        # Unless we explicitly test it, we don't want to use the cache during
        # testing.
        self.env.cache = False
        self.env.manifest = False

        # Setup a temporary settings object
        # TODO: This should be used (from 1.4), but the tests need
        # to run on 1.3 as well.
        # from django.test.utils import override_settings
        # self.override_settings = override_settings()
        # self.override_settings.enable()

    def teardown(self):
        #self.override_settings.disable()
        pass


def delsetting(name):
    """Helper to delete a Django setting from the settings
    object.

    Required because the Django 1.1. LazyObject does not implement
    __delattr__.
    """
    if '__delattr__' in settings.__class__.__dict__:
        delattr(settings, name)
    else:
        delattr(settings._wrapped, name)


class TestConfig(object):
    """The environment configuration is backed by the Django settings
    object.
    """

    def test_default_options(self):
        """The builtin options have different names within the Django
        settings, to make it obvious they belong to django-assets.
        """

        settings.ASSETS_URL_EXPIRE = True
        assert get_env().config['url_expire'] == settings.ASSETS_URL_EXPIRE

        settings.ASSETS_ROOT = 'FOO_ASSETS'
        settings.STATIC_ROOT = 'FOO_STATIC'
        settings.MEDIA_ROOT = 'FOO_MEDIA'
        # Pointing to ASSETS_ROOT
        assert get_env().directory == 'FOO_ASSETS'
        get_env().directory = 'BAR'
        assert settings.ASSETS_ROOT == 'BAR'
        # Pointing to STATIC_ROOT
        delsetting('ASSETS_ROOT')
        assert get_env().directory == 'FOO_STATIC'
        get_env().directory = 'BAR'
        assert settings.STATIC_ROOT == 'BAR'
        # Pointing to MEDIA_ROOT; Note we only
        # set STATIC_ROOT to None rather than deleting
        # it, a scenario that may occur in the wild.
        settings.STATIC_ROOT = None
        assert get_env().directory == 'FOO_MEDIA'
        get_env().directory = 'BAR'
        assert settings.MEDIA_ROOT == 'BAR'

    def test_custom_options(self):
        settings.FOO = 42
        assert get_env().config['foo'] == 42
        # Also, we are caseless.
        assert get_env().config['foO'] == 42

    def test_deprecated_options(self):
        try:
            django_env_reset()
            with check_warnings(("", ImminentDeprecationWarning)) as w:
                settings.ASSETS_EXPIRE = 'filename'
                assert_raises(DeprecationWarning, get_env)

            django_env_reset()
            with check_warnings(("", ImminentDeprecationWarning)) as w:
                settings.ASSETS_EXPIRE = 'querystring'
                assert get_env().url_expire == True

            with check_warnings(("", ImminentDeprecationWarning)) as w:
                django_env_reset()
                settings.ASSETS_UPDATER = 'never'
                assert get_env().auto_build == False
        finally:
            delsetting('ASSETS_EXPIRE')
            delsetting('ASSETS_UPDATER')

class TestTemplateTag():

    def setup(self):
        test_instance = self
        class MockBundle(Bundle):
            urls_to_fake = ['foo']
            def __init__(self, *a, **kw):
                Bundle.__init__(self, *a, **kw)
                self.env = get_env()
                # Kind of hacky, but gives us access to the last Bundle
                # instance used by our Django template tag.
                test_instance.the_bundle = self
            def urls(self, *a, **kw):
                return self.urls_to_fake
        # Inject our mock bundle class
        self._old_bundle_class = AssetsNode.BundleClass
        AssetsNode.BundleClass = self.BundleClass = MockBundle

        # Reset the Django asset environment, init it with some
        # dummy bundles.
        django_env_reset()
        self.foo_bundle = Bundle()
        self.bar_bundle = Bundle()
        django_env_register('foo_bundle', self.foo_bundle)
        django_env_register('bar_bundle', self.bar_bundle)

    def teardown(self):
        AssetsNode.BundleClass = self._old_bundle_class
        del self._old_bundle_class

    def render_template(self, args, ctx={}):
        return Template('{% load assets %}{% assets '+args+' %}{{ ASSET_URL }};{% endassets %}').render(Context(ctx))

    def test_reference_bundles(self):
        self.render_template('"foo_bundle", "bar_bundle"')
        assert self.the_bundle.contents == (self.foo_bundle, self.bar_bundle)

    def test_reference_files(self):
        self.render_template('"file1", "file2", "file3"')
        assert self.the_bundle.contents == ('file1', 'file2', 'file3',)

    def test_reference_mixed(self):
        self.render_template('"foo_bundle", "file2", "file3"')
        assert self.the_bundle.contents == (self.foo_bundle, 'file2', 'file3',)

    def test_with_vars(self):
        self.render_template('var1 var2', {'var1': self.foo_bundle, 'var2': 'a_file'})
        assert self.the_bundle.contents == (self.foo_bundle, 'a_file',)

    def test_debug_option(self):
        self.render_template('"file", debug="true"')
        assert self.the_bundle.debug == True
        self.render_template('"file", debug="false"')
        assert self.the_bundle.debug == False
        self.render_template('"file", debug="merge"')
        assert self.the_bundle.debug == "merge"

    def test_with_no_commas(self):
        """Using commas is optional.
        """
        self.render_template('"file1" "file2" "file3"')

    def test_output_urls(self):
        """Ensure the tag correcly spits out the urls the bundle returns.
        """
        self.BundleClass.urls_to_fake = ['foo', 'bar']
        assert self.render_template('"file1" "file2" "file3"') == 'foo;bar;'


class TestLoader(TempDirHelper):

    def setup(self):
        TempDirHelper.setup(self)

        self.loader = DjangoLoader()
        settings.TEMPLATE_LOADERS = [
            'django.template.loaders.filesystem.Loader',
        ]
        settings.TEMPLATE_DIRS = [self.tempdir]

    def test(self):
        self.create_files({
            'template.html': """
            {% load assets %}
            <h1>Test</h1>
            {% if foo %}
                {% assets "A" "B" "C" output="output.html" %}
                    {{ ASSET_URL }}
                {% endassets %}
            {% endif %}
            """
        })
        bundles = self.loader.load_bundles()
        assert len(bundles) == 1
        assert bundles[0].output == "output.html"


class TestStaticFiles(TempEnvironmentHelper):
    """Test integration with django.contrib.staticfiles.
    """

    def setup(self):
        TempEnvironmentHelper.setup(self)

        try:
            import django.contrib.staticfiles
        except ImportError:
            raise SkipTest()

        # Configure a staticfiles-using project.
        settings.STATIC_ROOT = settings.MEDIA_ROOT   # /media via baseclass
        settings.MEDIA_ROOT = self.path('needs_to_differ_from_static_root')
        settings.STATIC_URL = '/media/'
        settings.INSTALLED_APPS += ('django.contrib.staticfiles',)
        settings.STATICFILES_DIRS = tuple(self.create_directories('foo', 'bar'))
        settings.STATICFILES_FINDERS += ('django_assets.finders.AssetsFinder',)
        self.create_files({'foo/file1': 'foo', 'bar/file2': 'bar'})
        settings.DEBUG = True

        # Reset the finders cache after each run, since our
        # STATICFILES_DIRS change every time.
        from django.contrib.staticfiles import finders
        finders._finders.clear()

    def test_build(self):
        """Finders are used to find source files.
        """
        self.mkbundle('file1', 'file2', output="out").build()
        assert self.get("media/out") == "foo\nbar"

    def test_build_nodebug(self):
        """If debug is disabled, the finders are not used.
        """
        settings.DEBUG = False
        bundle = self.mkbundle('file1', 'file2', output="out")
        assert_raises(BundleError, bundle.build)

        # After creating the files in the static root directory,
        # it works (we only look there in production).
        from django.core.management import call_command
        call_command("collectstatic", interactive=False)

        bundle.build()
        assert self.get("media/out") == "foo\nbar"

    def test_missing_file(self):
        """An error is raised if a source file is missing.
        """
        bundle = self.mkbundle('xyz', output="out")
        assert_raises_regexp(
            BundleError, 'using staticfiles finders', bundle.build)

    def test_serve_built_files(self):
        """The files we write to STATIC_ROOT are served in debug mode
        using "django_assets.finders.AssetsFinder".
        """
        self.mkbundle('file1', 'file2', output="out").build()
        # I tried using the test client for this, but it would
        # need to be setup using StaticFilesHandler, which is
        # incompatible with the test client.
        from django_assets.finders import AssetsFinder
        assert AssetsFinder().find('out') == self.path("media/out")

    def test_css_rewrite(self):
        """Test that the cssrewrite filter can deal with staticfiles.
        """
        # file1 is in ./foo, file2 is in ./bar, the output will be
        # STATIC_ROOT = ./media
        self.create_files(
                {'foo/css': 'h1{background: url("file1"), url("file2")}'})
        self.mkbundle('css', filters='cssrewrite', output="out").build()
        # The urls are NOT rewritte to foo/file1, but because all three
        # directories are essentially mapped into the same url space, they
        # remain as is.
        assert self.get('media/out') == \
                '''h1{background: url("file1"), url("file2")}'''


class TestFilter(TempEnvironmentHelper):

    def test_template(self):
        self.create_files({'media/foo.html': '{{ num|filesizeformat }}'})
        self.mkbundle('foo.html', output="out",
                      filters=get_filter('template', context={'num': 23232323})).build()
        assert self.get('media/out') == '22.2 MB'
