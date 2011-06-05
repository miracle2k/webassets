"""Contains the core functionality that manages merging of assets.
"""

import os
import urllib2
try:
    import cStringIO as StringIO
except:
    import StringIO


import sys
if sys.version_info >= (2, 5):
    import hashlib
    md5_constructor = hashlib.md5
else:
    import md5
    md5_constructor = md5.new


__all__ = ('FileHunk', 'MemoryHunk', 'make_url', 'merge', 'apply_filters')


class BaseHunk(object):
    """Abstract base class.
    """

    def mtime(self):
        raise NotImplementedError()

    def key(self):
        """Return a key we can use to cache this hunk.
        """
        # MD5 is faster than sha, and we don't care so much about collisions.
        # We care enough however not to use hash().
        md5 = md5_constructor()
        md5.update(self.data())
        return md5.hexdigest()

    def data(self):
        raise NotImplementedError()


class FileHunk(BaseHunk):
    """Exposes a single file through as a hunk.
    """

    def __init__(self, filename):
        self.filename = filename

    def mtime(self):
        pass

    def data(self):
        f = open(self.filename, 'rb')
        try:
            return f.read()
        finally:
            f.close()


class UrlHunk(BaseHunk):
    """Represents a file that is referenced by an Url.
    """

    def __init__(self, url):
        self.url = url

    def data(self):
        if not hasattr(self, '_data'):
            r = urllib2.urlopen(self.url)
            try:
                self._data = r.read()
            finally:
                r.close()
        return self._data


class MemoryHunk(BaseHunk):
    """Content that is no longer a direct representation of
    a source file. It might have filters applied, and is probably
    the result of merging multiple individual source files together.
    """

    def __init__(self, data, files=[]):
        self._data = data
        self.files = files

    def mtime(self):
        pass

    def data(self):
        return self._data

    def save(self, filename):
        f = open(filename, 'wb')
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


def apply_filters(hunk, filters, type, cache=None, no_cache_read=False,
                  **kwargs):
    """Apply the given list of filters to the hunk, returning a new
    ``MemoryHunk`` object.

    If ``no_cache_read`` is given, then the cache will not be
    considered for this operation (though the result will still be
    written to the cache).

    ``kwargs`` are options that should be passed along to the filters.
    If ``hunk`` is a file hunk, a ``source_path`` key will automatically
    be added to ``kwargs``.
    """
    assert type in ('input', 'output')

    # Short-circuit
    # TODO: This can actually be improved by looking at "type" and
    # whether any of the existing filters handles this type.
    if not filters:
        return hunk

    if cache:
        key = ("hunk", hunk.key(), tuple(filters), type)
        if not no_cache_read:
            content = cache.get(key)
            if not content in (False, None):
                return MemoryHunk(content)

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

    # Note that the key used to cache this hunk is different from the key
    # the hunk will expose to subsequent merges, i.e. hunk.key() is always
    # based on the actual content, and does not match the cache key. The
    # latter also includes information about for example the filters used.
    #
    # It wouldn't have to be this way. Hunk could subsequently expose their
    # cache key through hunk.key(). This would work as well, but would be
    # an inferior solution: Imagine a source file which receives
    # non-substantial changes, in the sense that they do not affect the
    # filter output, for example whitespace. If a hunk's key is the cache
    # key, such a change would invalidate the caches for all subsequent
    # operations on this hunk as well, even though it didn't actually change
    # after all.
    content = data.getvalue()
    if cache:
        cache.set(key, content)
    return MemoryHunk(content)


def make_url(env, filename, expire=True):
    """Return a output url, modified for expire header handling.

    Set ``expire`` to ``False`` if you do not want the URL to
    be modified for cache busting.
    """
    if expire:
        path = env.abspath(filename)
        if env.expire == 'querystring':
            last_modified = os.stat(path).st_mtime
            result = "%s?%d" % (filename, last_modified)
        elif env.expire == 'filename':
            last_modified = os.stat(path).st_mtime
            name = filename.rsplit('.', 1)
            if len(name) > 1:
                result = "%s.%d.%s" % (name[0], last_modified, name[1])
            else:
                result = "%s.%d" % (name, last_modified)
        elif not env.expire:
            result = filename
        else:
            raise ValueError('Unknown value for ASSETS_EXPIRE option: %s' %
                                 env.expire)
    else:
        result = filename
    return env.absurl(result)


def merge_filters(filters1, filters2):
    """Merge two filter lists into one.

    Duplicate filters are removed. Since filter order is important,
    the order of the arguments to this function also matter. Duplicates
    are always removed from the second filter set if they exist in the
    first.

    The result will always be ``filters1``, with additional unique
    filters from ``filters2`` appended. Within the context of a
    hierarchy, you want ``filters2`` to be the parent.

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
