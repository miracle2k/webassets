"""Explicit alias for the 'yui' filter, which defaults to Javascript mode
by default.
"""

from django_assets.filter import yui

def apply(_in, out):
    return yui.apply(_in, out, mode='js')