"""Contains the core functionality that manages merging of assets.
"""

import urllib2
try:
    import cStringIO as StringIO
except:
    import StringIO


__all__ = ('FileHunk', 'MemoryHunk', 'merge', 'FilterTool',
           'MoreThanOneFilterError')


class BaseHunk(object):
    """Abstract base class.
    """

    def mtime(self):
        raise NotImplementedError()

    def __hash__(self):
        return hash(self.data())

    def __eq__(self, other):
        if isinstance(other, BaseHunk):
            # Allow class to be used as a unique dict key.
            return hash(self) == hash(other)
        return False

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

    def __init__(self, data, files=None):
        self._data = data
        self.files = files or []

    def mtime(self):
        pass

    def data(self):
        if hasattr(self._data, 'read'):
            return self._data.read()
        return self._data

    def save(self, filename):
        f = open(filename, 'wb')
        try:
            f.write(self.data())
        finally:
            f.close()


def merge(hunks, separator=None):
    """Merge the given list of hunks, returning a new ``MemoryHunk``
    object.
    """
    # TODO: combine the list of source files, we'd like to collect them
    # The linebreak is important in certain cases for Javascript
    # files, like when a last line is a //-comment.
    if not separator:
        separator = '\n'
    return MemoryHunk(separator.join([h.data() for h in hunks]))


class MoreThanOneFilterError(Exception):

    def __init__(self, message, filters):
        Exception.__init__(self, message)
        self.filters = filters


class FilterTool(object):
    """Can apply filters to hunk objects, while using the cache.

    If ``no_cache_read`` is given, then the cache will not be
    considered for this operation (though the result will still be
    written to the cache).

    ``kwargs`` are options that should be passed along to the filters.
    """

    VALID_TRANSFORMS = ('input', 'output',)
    VALID_FUNCS =  ('open', 'concat',)

    def __init__(self, cache=None, no_cache_read=False, kwargs=None):
        self.cache = cache
        self.no_cache_read = no_cache_read
        self.kwargs = kwargs or {}

    def _wrap_cache(self, key, func):
        """Return cache value ``key``, or run ``func``.
        """
        if self.cache:
            if not self.no_cache_read:
                content = self.cache.get(key)
                if not content in (False, None):
                    return MemoryHunk(content)

        content = func().getvalue()
        if self.cache:
            self.cache.set(key, content)
        return MemoryHunk(content)

    def apply(self, hunk, filters, type, kwargs=None):
        """Apply the given list of filters to the hunk, returning a new
        ``MemoryHunk`` object.

        ``kwargs`` are options that should be passed along to the filters.
        If ``hunk`` is a file hunk, a ``source_path`` key will automatically
        be added to ``kwargs``.
        """
        assert type in self.VALID_TRANSFORMS

        filters = [f for f in filters if hasattr(f, type)]
        if not filters:  # Short-circuit
            return hunk

        def func():
            kwargs_final = self.kwargs.copy()
            kwargs_final.update(kwargs or {})
            if hasattr(hunk, 'filename'):
                kwargs_final.setdefault('source_path', hunk.filename)

            data = StringIO.StringIO(hunk.data())
            for filter in filters:
                out = StringIO.StringIO()
                getattr(filter, type)(data, out, **kwargs_final)
                data = out
                data.seek(0)

            return data

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
        # operations on this hunk as well, even though it didn't actually
        # change after all.
        key = ("hunk", hunk, tuple(filters), type)
        return self._wrap_cache(key, func)

    def apply_func(self, filters, type, args, kwargs=None):
        """Apply a filter that is not a transform (stream in,
        stream out). Instead, is supposed to operate on argument
        ``args`` and should then produce an output stream.

        Only one such filter can run per operation.
        """
        assert type in self.VALID_FUNCS

        filters = [f for f in filters if hasattr(f, type)]
        if not filters:  # Short-circuit
            return None

        if len(filters) > 1:
            raise MoreThanOneFilterError(
                'These filters cannot be combined: %s' % (
                    ', '.join([f.name for f in filters])), filters)

        def func():
            filter = filters[0]
            out = StringIO.StringIO()
            kwargs_final = self.kwargs.copy()
            kwargs_final.update(kwargs or {})
            getattr(filter, type)(out, *args, **kwargs_final)
            return out

        key = ("hunk", args, tuple(filters), type)
        return self._wrap_cache(key, func)


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
