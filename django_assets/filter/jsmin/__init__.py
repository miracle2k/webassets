"""Minifies Javascript by removing whitespace, comments, etc.

Based on Baruch Even's port of Douglas Crockford's `JSMin
<http://www.crockford.com/javascript/jsmin.html>`_, which is
included, so no external dependency is required.
"""

from jsmin import JavascriptMinify

def apply(_in, out):
    JavascriptMinify().minify(_in, out)