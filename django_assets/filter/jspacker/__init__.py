"""Reduces the size of Javascript using an inline compression algorithm,
i.e. the script will be unpacked on the client side by the browser.

Based on Dean Edwards' `jspacker 2 <http://dean.edwards.name/packer/>`_, 
as ported by Florian Schulze.
"""

from jspacker import JavaScriptPacker

def apply(_in, out):
    out.write(JavaScriptPacker().pack(_in.read(),
                                      compaction=False,
                                      encoding=62,
                                      fastDecode=True))