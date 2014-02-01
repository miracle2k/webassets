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
        self.env.register_renderer('custom', '<{url}>', '[{url}]')

    def test_missing_renderer(self):
        b = self.MockBundle('a', output='out', renderer='no-such-renderer')
        with self.assertRaises(ValueError) as cm:
            [r.render() for r in b.renderers()]
        self.assertEqual(
            str(cm.exception), 'Cannot find renderer "no-such-renderer"')

    def test_reference_css(self):
        b = self.MockBundle('a', output='out.css', renderer='css')
        self.assertEqual(
            [r.render() for r in b.renderers()],
            ['<link rel="stylesheet" type="text/css" href="/out.css"/>'])

    def test_reference_js(self):
        b = self.MockBundle('a', output='out.js', renderer='js')
        self.assertEqual(
            [r.render() for r in b.renderers()],
            ['<script type="text/javascript" src="/out.js"></script>'])

    def test_reference_custom(self):
        b = self.MockBundle('a', output='out.cstm', renderer='custom')
        self.assertEqual(
            [r.render() for r in b.renderers()],
            ['</out.cstm>'])

    def test_inline_css(self):
        b = self.MockBundle('a', output='out.css', renderer='css',
                            extra=dict(data='some-css'))
        self.assertEqual(
            [r.render(inline=True) for r in b.renderers()],
            ['''\
<style type="text/css"><!--/*--><![CDATA[/*><!--*/
some-css
/*]]>*/--></style>'''])

    def test_inline_js(self):
        b = self.MockBundle('a', output='out.js', renderer='js',
                            extra=dict(data='some-js'))
        self.assertEqual(
            [r.render(inline=True) for r in b.renderers()],
            ['''\
<script type="text/javascript"><!--//--><![CDATA[//><!--
some-js
//--><!]]></script>'''])

    def test_defaultinline_custom(self):
        b = self.MockBundle('a', output='a.out', renderer='custom')
        self.assertEqual(
            [r.render() for r in b.renderers(inline=True)],
            ['[/a.out]'])

    def test_inherit(self):
        a = self.MockBundle('a', output='a.out')
        b = self.MockBundle('b', output='b.out')
        c = self.MockBundle(a, b, output='c.out')
        self.assertEqual(
            [r.render() for r in c.renderers(default='custom')],
            ['</c.out>'])

    def test_inherit_debug(self):
        self.env.debug = True
        a = self.MockBundle('a', output='a.out')
        b = self.MockBundle('b', output='b.out')
        c = self.MockBundle(a, b, output='c.out')
        self.assertEqual(
            [r.render() for r in c.renderers(default='custom')],
            ['</a>', '</b>'])

    def test_multiple(self):
        a = self.MockBundle('a', output='a.out', renderer='custom')
        b = self.MockBundle('b', output='b.out', renderer='custom')
        c = self.MockBundle(a, b, output='c.out', renderer='custom')
        self.assertEqual(
            [r.render() for r in c.renderers(inline=False)],
            ['</c.out>'])
        self.assertEqual(
            [r.render() for r in c.renderers(inline=True)],
            ['[/c.out]'])

    def test_multiple_debug(self):
        self.env.debug = True
        a = self.MockBundle('a', output='a.out', renderer='custom')
        b = self.MockBundle('b', output='b.out', renderer='custom')
        c = self.MockBundle(a, b, output='c.out', renderer='custom')
        self.assertEqual(
            [r.render() for r in c.renderers(inline=False)],
            ['</a>', '</b>'])
        self.assertEqual(
            [r.render() for r in c.renderers(inline=True)],
            ['[/a]', '[/b]'])

    def test_mixed(self):
        self.env.register_renderer('custom2', '<<{url}>>', '[[{url}]]')
        a = self.MockBundle('a', output='a.out', renderer='custom')
        b = self.MockBundle('b', output='b.out', renderer='custom2')
        c = self.MockBundle(a, b, output='c.out', renderer='custom')
        self.assertEqual(
            [r.render() for r in c.renderers(inline=False)],
            ['</c.out>', '<</b.out>>'])
        self.assertEqual(
            [r.render() for r in c.renderers(inline=True)],
            ['[/c.out]', '[[/b.out]]'])

    def test_mixed_debug(self):
        self.env.debug = True
        self.env.register_renderer('custom2', '<<{url}>>', '[[{url}]]')
        a = self.MockBundle('a', output='a.out', renderer='custom')
        b = self.MockBundle('b', output='b.out', renderer='custom2')
        c = self.MockBundle(a, b, output='c.out', renderer='custom')
        self.assertEqual(
            [r.render() for r in c.renderers(inline=False)],
            ['</a>', '<</b>>'])
        self.assertEqual(
            [r.render() for r in c.renderers(inline=True)],
            ['[/a]', '[[/b]]'])

    def test_mixed_interleaved(self):
        self.env.register_renderer('custom2', '<<{url}>>', '[[{url}]]')
        a = self.MockBundle('a', output='a.out', renderer='custom')
        b = self.MockBundle('b', output='b.out', renderer='custom2')
        c = self.MockBundle('c', output='c.out', renderer='custom')
        d = self.MockBundle(a, b, c, output='d.out', renderer='custom')
        self.assertEqual(
            [r.render() for r in d.renderers(inline=False)],
            ['</d.out>', '<</b.out>>', '</d.out.part-1>'])
        self.assertEqual(
            [r.render() for r in d.renderers(inline=True)],
            ['[/d.out]', '[[/b.out]]', '[/d.out.part-1]'])

    def test_mixed_interleaved_debug(self):
        self.env.debug = True
        self.env.register_renderer('custom2', '<<{url}>>', '[[{url}]]')
        a = self.MockBundle('a', output='a.out', renderer='custom')
        b = self.MockBundle('b', output='b.out', renderer='custom2')
        c = self.MockBundle('c', output='c.out', renderer='custom')
        d = self.MockBundle(a, b, c, output='d.out', renderer='custom')
        self.assertEqual(
            [r.render() for r in d.renderers(inline=False)],
            ['</a>', '<</b>>', '</c>'])
        self.assertEqual(
            [r.render() for r in d.renderers(inline=True)],
            ['[/a]', '[[/b]]', '[/c]'])
