from nose.plugins.skip import SkipTest
from webassets import Environment as AssetsEnvironment, Bundle
from webassets.test import TempEnvironmentHelper


try:
    import jinja2
except ImportError:
    raise SkipTest('Jinja2 not installed')
else:
    from jinja2 import Template, Environment as JinjaEnvironment
    from webassets.ext.jinja2 import AssetsExtension, Jinja2Loader


class TestTemplateTag(object):

    def setup(self):
        # Setup the assets environment.
        assets_env = AssetsEnvironment('', '')
        self.foo_bundle = Bundle()
        self.bar_bundle = Bundle()
        assets_env.register('foo_bundle', self.foo_bundle)
        assets_env.register('bar_bundle', self.bar_bundle)

        # Inject a mock bundle class into the Jinja2 extension, so we
        # can check on what exactly it does.
        test_instance = self
        class MockBundle(Bundle):
            urls_to_fake = ['foo']
            def __init__(self, *a, **kw):
                Bundle.__init__(self, *a, **kw)
                self.env = assets_env

                self.dbg = kw.get('debug', None)

                # Kind of hacky, but gives us access to the last Bundle
                # instance used by the extension.
                test_instance.the_bundle = self
            def urls(self, *a, **kw):
                return self.urls_to_fake
        self._old_bundle_class = AssetsExtension.BundleClass
        AssetsExtension.BundleClass = self.BundleClass = MockBundle

        # Setup the Jinja2 environment.
        self.jinja_env = JinjaEnvironment()
        self.jinja_env.add_extension(AssetsExtension)
        self.jinja_env.assets_environment = assets_env

    def teardown(self):
        AssetsExtension.BundleClass = self._old_bundle_class
        del self._old_bundle_class

    def render_template(self, args, ctx=None):
        return self.jinja_env.from_string(
            '{% assets '+args+' %}{{ ASSET_URL }};{% endassets %}')\
                .render(ctx or {})

    def test_reference_bundles(self):
        self.render_template('"foo_bundle", "bar_bundle"')
        assert self.the_bundle.contents == (self.foo_bundle, self.bar_bundle)

    def test_reference_files(self):
        self.render_template('"file1", "file2", "file3"')
        assert self.the_bundle.contents == ('file1', 'file2', 'file3',)

    def test_reference_files_list(self):
        self.render_template('["file1", "file2", "file3"]')
        assert self.the_bundle.contents == ('file1', 'file2', 'file3',)

    def test_reference_files_tuple(self):
        self.render_template('("file1", "file2", "file3")')
        assert self.the_bundle.contents == ('file1', 'file2', 'file3',)

    def test_reference_files_mixed(self):
        self.render_template('"file1", ("file2", "file3")')
        assert self.the_bundle.contents == ('file1', 'file2', 'file3',)

    def test_reference_mixed(self):
        self.render_template('"foo_bundle", "file2", "file3"')
        assert self.the_bundle.contents == (self.foo_bundle, 'file2', 'file3',)

    def test_with_vars(self):
        self.render_template('var1, var2', {'var1': self.foo_bundle, 'var2': 'a_file'})
        assert self.the_bundle.contents == (self.foo_bundle, 'a_file',)

    def test_output_urls(self):
        """Ensure the tag correctly spits out the urls the bundle returns.
        """
        self.BundleClass.urls_to_fake = ['foo', 'bar']
        assert self.render_template('"file1" "file2" "file3"') == 'foo;bar;'

    def test_debug_on_tag(self):
        content = self.jinja_env.from_string(
            '{% assets debug="True", "debug1.txt" %}{{ ASSET_URL }};{% endassets %}').render({})
        assert self.the_bundle.dbg == 'True'

    def test_extra_values(self):
        self.foo_bundle.extra = {'moo': 42}
        output = self.jinja_env.from_string(
            '{% assets "foo_bundle" %}{{ EXTRA.moo }}{% endassets %}').render()
        assert output == '42'


class TestLoader(TempEnvironmentHelper):

    default_files = {
        'template.html': """
            <h1>Test</h1>
            {% if foo %}
                {% assets "A", "B", "C", output="output.html" %}
                    {{ ASSET_URL }}
                {% endassets %}
            {% endif %}
            """
    }

    def setup(self):
        TempEnvironmentHelper.setup(self)
        self.jinja_env = JinjaEnvironment()
        self.jinja_env.add_extension(AssetsExtension)
        self.jinja_env.assets_environment = self.env

    def test(self):
        loader = Jinja2Loader(self.env, [self.tempdir], [self.jinja_env])
        bundles = loader.load_bundles()
        assert len(bundles) == 1
        assert bundles[0].output == "output.html"
