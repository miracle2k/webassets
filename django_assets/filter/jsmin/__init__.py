"""Minify Javascript assets (removes whitespace, comments, etc).

Based on Baruch Even's port of Douglas Crockford's JSMin:
    http://www.crockford.com/javascript/jsmin.html
"""

from jsmin import JavascriptMinify

def apply(_in, out):
    JavascriptMinify().minify(_in, out)