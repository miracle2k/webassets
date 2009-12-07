from jsmin import JavascriptMinify
from django_assets.filter import Filter


__all__ = ('JSMinFilter',)


class JSMinFilter(Filter):
    """Minifies Javascript by removing whitespace, comments, etc.

    Based on Baruch Even's port of Douglas Crockford's `JSMin
    <http://www.crockford.com/javascript/jsmin.html>`_, which is
    included, so no external dependency is required.
    """

    name = 'jsmin'

    def apply(self, _in, out):
        JavascriptMinify().minify(_in, out)