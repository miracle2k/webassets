"""Minify Javascript and CSS with
`YUI Compressor <http://developer.yahoo.com/yui/compressor/>`_.

This filter defaults to JS mode, but it is recommended that you explicitly
specify ``yui_js`` instead. Use ``yui_css`` to compress CSS files.

YUI Compressor is an external tool written in Java, which needs to be
available. You can define a ``YUI_COMPRESSOR_PATH`` setting that points to
the ``.jar`` file. Otherwise, an environment variable by the same name is
tried. The filter will also look for a ``JAVA_HOME`` environment variable
to run the ``.jar`` file, or will otherwise assume that ``java`` is on the
system path.
"""

from django_assets.filter import yui_js

def apply(_in, out):
    return yui_js.apply(_in, out)