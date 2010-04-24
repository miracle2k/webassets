"""Contains the core functionality that manages merging of assets.
"""

import os
try:
    import cStringIO as StringIO
except:
    import StringIO
import urlparse
from django_assets.conf import settings


__all__ = ('FileHunk', 'MemoryHunk', 'make_url', 'merge', 'apply_filters')


def absurl(fragment):
    """Create an absolute url based on MEDIA_URL.
    """
    root = settings.MEDIA_URL
    root += root[-1:] != '/' and '/' or ''
    return urlparse.urljoin(root, fragment)


def abspath(filename):
    """Create an absolute path based on MEDIA_ROOT.
    """
    if os.path.isabs(filename):
        return filename
    return os.path.abspath(os.path.join(settings.MEDIA_ROOT, filename))


class BaseHunk(object):
    """Abstract base class.
    """

    def mtime(self):
        raise NotImplementedError()

    def key(self):
        raise NotImplementedError()

    def data(self):
        raise NotImplementedError()


class FileHunk(BaseHunk):
    """Exposes a single file through as a hunk.
    """

    def __init__(self, filename):
        self.filename = abspath(filename)

    def key(self):
        pass

    def mtime(self):
        pass

    def data(self):
        f = open(self.filename, 'rb')
        try:
            return f.read()
        finally:
            f.close()


class MemoryHunk(BaseHunk):
    """Content that is no longer a direct representation of
    a source file. It might have filters applied, and is probably
    the result of merging multiple individual source files together.
    """

    def __init__(self, data, files=[]):
        self._data = data
        self.files = files

    def key(self):
        return hash(self._data)

    def mtime(self):
        pass

    def data(self):
        return self._data

    def save(self, filename):
        f = open(abspath(filename), 'wb')
        try:
            f.write(self.data())
        finally:
            f.close()


def merge(hunks):
    """Merge the given list of hunks, returning a new ``MemoryHunk``
    object.
    """
    # TODO: combine the list of source files, we'd like to collect them
    # The linebreak is important in certain cases for Javascript
    # files, like when a last line is a //-comment.
    return MemoryHunk("\n".join([h.data() for h in hunks]))


def apply_filters(hunk, filters, type, **kwargs):
    """Apply the given list of filters to the hunk, returning a new
    ``MemoryHunk`` object.

    ``kwargs`` are options that should be passed along to the filters.
    If ``hunk`` is a file hunk, a ``source_path`` key will automatically
    be added to ``kwargs``.
    """
    assert type in ('input', 'output')

    kwargs = kwargs.copy()
    if hasattr(hunk, 'filename'):
        kwargs.setdefault('source_path', hunk.filename)

    data = StringIO.StringIO(hunk.data())
    for filter in filters:
        func = getattr(filter, type, False)
        if func:
            out = StringIO.StringIO()
            func(data, out, **kwargs)
            data = out
            data.seek(0)

    return MemoryHunk(data.getvalue())


def make_url(filename, expire=True):
    """Return a output url, modified for expire header handling.

    Set ``expire`` to ``False`` if you do not want the URL to
    be modified for cache busting.
    """
    if expire:
        path = abspath(filename)
        if settings.ASSETS_EXPIRE == 'querystring':
            last_modified = os.stat(path).st_mtime
            result = "%s?%d" % (filename, last_modified)
        elif settings.ASSETS_EXPIRE == 'filename':
            last_modified = os.stat(path).st_mtime
            name = filename.rsplit('.', 1)
            if len(name) > 1:
                result = "%s.%d.%s" % (name[0], last_modified, name[1])
            else:
                result = "%s.%d" % (name, last_modified)
        elif not settings.ASSETS_EXPIRE:
            result = filename
        else:
            raise ValueError('Unknown value for ASSETS_EXPIRE option: %s' %
                                settings.ASSETS_EXPIRE)
    else:
        result = filename
    return absurl(result)


def merge_filters(filters1, filters2):
    """Merge two filter lists into one.

    Duplicate filters are removed. Since filter order is important,
    the order of the arguments to this function also matter. Duplicates
    are always removed from the second filter set if they exist in the
    first.

    This function presumes that all the given filters inherit from
    ``Filter``, which properly implements operators to determine
    duplicate filters.
    """
    result = list(filters1[:])
    if filters2:
        for f in filters2:
            if not f in result:
                result.append(f)
    return result
