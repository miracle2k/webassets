from __future__ import absolute_import
from webassets.filter import Filter

__all__ = ('CSSPrefixerFilter',)


class CSSPrefixerFilter(Filter):
    """Uses `CSSPrefixer <http://github.com/myfreeweb/cssprefixer/>`_
    to add vendor prefixes to CSS files.
    """

    name = 'cssprefixer'

    def setup(self):
        import cssprefixer
        self.cssprefixer = cssprefixer

    def output(self, _in, out, **kw):
        out.write(self.cssprefixer.process(_in.read(), False, False))
