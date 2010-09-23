from __future__ import absolute_import
from webassets.filter import Filter

__all__ = ('CleverCSSFilter',)


class CleverCSSFilter(Filter):
    """Converts `CleverCSS <http://sandbox.pocoo.org/clevercss/>`_ markup
    to real CSS.

    If you want to combine it with other CSS filters, make sure this one
    runs first.
    """

    name = 'clevercss'

    def setup(self):
        import clevercss
        self.clevercss = clevercss

    def output(self, _in, out, **kw):
        out.write(self.clevercss.convert(_in.read()))
