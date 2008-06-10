"""Reduces the size of Javascript by using an inline compression algorithm,
i.e. the original script is unpacked by the client.

Based on Dean Edwards' jspacker 2, ported by Florian Schulze:
    http://dean.edwards.name/packer/
"""

from jspacker import JavaScriptPacker

def apply(_in, out):
    out.write(JavaScriptPacker().pack(_in.read(),
                                      compaction=False,
                                      encoding=62,
                                      fastDecode=True))