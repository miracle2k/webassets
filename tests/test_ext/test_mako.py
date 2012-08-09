from webassets import Environment as AssetsEnvironment, Bundle

class TestTemplateTag(object):
    def setup(self):
        assets_env = AssetsEnvironment('', '')

        test_instance = self

        class MockBundle(Bundle):
            urls_to_fake = ['http://google.com']
            def __init__(self, *a, **kw):
                Bundle.__init__(self, *a, **kw)
                self.env = assets_env

                self.dbg = kw.get('debug', None)

                # Kind of hacky, but gives us access to the last Bundle
                # instance used by the extension.
                test_instance.the_bundle = self
            def urls(self, *a, **kw):
                return self.urls_to_fake

        self.foo_bundle = MockBundle()
        self.bar_bundle = MockBundle()
        assets_env.register('foo_bundle', self.foo_bundle)
        assets_env.register('bar_bundle', self.bar_bundle)


        self.assets_env = assets_env

    def test_render_template_with_one_bundle(self):
        from mako.template import Template
        mytemplate = Template("""
        <%namespace name="assets" module="webassets.ext.mako"/>

        <%assets:assets bundles="foo_bundle", env="${env}", args="ASSETS_URL">
            ${ASSETS_URL}
        </%assets:assets>

        """)

        result = mytemplate.render(env=self.assets_env)
        assert 'http://google.com' in result
