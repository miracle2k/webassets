from jspacker import JavaScriptPacker
from django_assets.filter import Filter


__all__ = ('JSPackerFilter',)


class JSPackerFilter(Filter):
    """Reduces the size of Javascript using an inline compression
    algorithm, i.e. the script will be unpacked on the client side
    by the browser.

    Based on Dean Edwards' `jspacker 2 <http://dean.edwards.name/packer/>`_,
    as ported by Florian Schulze.
    """
    # TODO: This could support options.

    name = 'jspacker'

    def apply(self, _in, out):
        out.write(JavaScriptPacker().pack(_in.read(),
                                          compaction=False,
                                          encoding=62,
                                          fastDecode=True))