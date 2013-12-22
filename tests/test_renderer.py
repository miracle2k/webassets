'''
Tests for the "rendering" aspect of :class:`Bundle` via
:class:`BundleRenderer`.
'''


import unittest
import sys

from tests.test_bundle_urls import BaseUrlsTester

class TestRenderer(BaseUrlsTester, unittest.TestCase):

    def setUp(self):
        self.setup()
        class MockBundleWithContent(self.MockBundle):
            def _build(self, *a, **kw):
                super(MockBundleWithContent, self)._build(*a, **kw)
                output = kw.get('output')
                if output:
                    output.write(self.extra.get('data', 'MockData'))
        self.MockBundle = MockBundleWithContent

    def test_missing_renderer(self):
        b = self.MockBundle('a', output='out', renderer='no-such-renderer')
        with self.assertRaises(ValueError) as cm:
            [r.render() for r in b.renderers()]
        self.assertEqual(
            str(cm.exception), 'Cannot find renderer "no-such-renderer"')

    def test_render_reference_css(self):
        b = self.MockBundle('a.css', output='out.css', renderer='css')
        self.assertEqual(
            [r.render() for r in b.renderers()],
            ['<link rel="stylesheet" type="text/css" href="/out.css"/>'])

    def test_render_reference_js(self):
        b = self.MockBundle('a.js', output='out.js', renderer='js')
        self.assertEqual(
            [r.render() for r in b.renderers()],
            ['<script type="text/javascript" src="/out.js"></script>'])

    def test_render_reference_custom(self):
        self.env.register_renderer('custom', '[REF: {url}]', '[RAW: {url}]')
        b = self.MockBundle('a.cstm', output='out.cstm', renderer='custom')
        self.assertEqual(
            [r.render() for r in b.renderers()],
            ['[REF: /out.cstm]'])

    def test_render_inline_css(self):
        b = self.MockBundle('a.css', output='out.css', renderer='css',
                            extra=dict(data='some-css'))
        self.assertEqual(
            [r.render(inline=True) for r in b.renderers()],
            ['''\
<style type="text/css"><!--/*--><![CDATA[/*><!--*/
some-css
/*]]>*/--></style>'''])

    def test_render_inline_js(self):
        b = self.MockBundle('a.js', output='out.js', renderer='js',
                            extra=dict(data='some-js'))
        self.assertEqual(
            [r.render(inline=True) for r in b.renderers()],
            ['''\
<script type="text/javascript"><!--//--><![CDATA[//><!--
some-js
//--><!]]></script>'''])

    def test_render_defaultinline_custom(self):
        self.env.register_renderer('custom', '[REF: {url}]', '[RAW: {url}]')
        b = self.MockBundle('a.cstm', output='out.cstm', renderer='custom')
        self.assertEqual(
            [r.render() for r in b.renderers(inline=True)],
            ['[RAW: /out.cstm]'])
