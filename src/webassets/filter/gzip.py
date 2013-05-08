from webassets import six
if six.PY3:
    # We do not support Python 3 right now, because the webassets pipeline
    # no longer supports operating on byte streams.
    raise ImportError("The gzip filter is not available on Python 3")


from __future__ import absolute_import

import gzip
from webassets.filter import Filter


__all__ = ('GZip',)


class GZip(Filter):
    """Applies gzip compression to the content given.

    This can be used if you are unable to let the webserver do the
    compression  on the fly, or just want to do precaching for additional
    performance.

    Note that you will still need to configure your webserver to send
    the files out marked as gzipped.
    """

    name = 'gzip'

    def output(self, _in, out, **kw):
        zfile = gzip.GzipFile(mode='wb', compresslevel=6, fileobj=out)
        try:
            zfile.write(_in.read())
        finally:
            zfile.close()
