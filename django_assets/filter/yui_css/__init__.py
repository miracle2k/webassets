"""Minify CSS using YUI Compressor.

See the ``yui`` filter for more information.
"""

from django_assets.filter import yui

def apply(_in, out):
    return yui.apply(_in, out, mode='css')