from __future__ import absolute_import
from webassets.filter import Filter


__all__ = ('RJSMinFilter',)


class RJSMinFilter(Filter):
    """Minifies Javascript by removing whitespace, comments, etc.

    Uses the `rJSmin library <http://opensource.perlig.de/rjsmin/>`_,
    which needs to be installed.

    ``rJSmin`` is based on Douglas Crockford's JS
    Based on Baruch Even's port of Douglas Crockford's `JSMin
    <http://www.crockford.com/javascript/jsmin.html>`_, which is
    also available as the ``jsmin`` filter.
    """

    name = 'rjsmin'

    def setup(self):
        import rjsmin
        self.rjsmin = rjsmin

    def output(self, _in, out, **kw):
        out.write(self.rjsmin.jsmin(_in.read()))
