"""GZips the contents of your asset.

This can be used if you are unable to let the webserver to the compression on
the fly, or just want to have them precached for performance.
"""

import gzip

def apply(_in, out):
    zfile = gzip.GzipFile(mode='wb', compresslevel=6, fileobj=out)
    try:
        zfile.write(_in.read())
    finally:
        zfile.close()