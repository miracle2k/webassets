import os
import re
from os.path import join, normpath
from webassets.filter import Filter
from webassets.utils import common_path_prefix


__all__ = ()


def addsep(path):
    """Add a trailing path separator."""
    if path and path[-1] != os.path.sep:
        return path + os.path.sep
    return path


def path2url(path):
    """Simple helper for NT systems to replace slash syntax."""
    if os.name == 'nt':
        return path.replace('\\', '/')
    return path


class PatternRewriter(Filter):
    """Base class for input filters which want to replace certain patterns.
    """

    # Define the patterns in the form of:
    #   method to call -> pattern to call it for (as a compiled regex)
    patterns = {}

    def input(self, _in, out, **kw):
        content = _in.read()
        for func, pattern in self.patterns.items():
            if not callable(func):
                func = getattr(self, func)
            # Should this pass along **kw? How many subclasses would need it?
            # As is, subclasses needing access need to overwrite input() and
            # set class attributes.
            content = pattern.sub(func, content)
        out.write(content)


urltag_re = re.compile(r"""
url\(
  (\s*)                 # allow whitespace wrapping (and capture)
  (                     # capture actual url
    [^\)\\\r\n]*?           # don't allow newlines, closing paran, escape chars (1)
    (?:\\.                  # process all escapes here instead
        [^\)\\\r\n]*?           # proceed, with previous restrictions (1)
    )*                     # repeat until end
  )
  (\s*)                 # whitespace again (and capture)
\)

# (1) non-greedy to let the last whitespace group capture something
# TODO: would it be faster to handle whitespace within _rewrite()?
""", re.VERBOSE)


class CSSUrlRewriter(PatternRewriter):
    """Base class for input filters which need to replace url() statements
    in CSS stylesheets.
    """

    patterns = {
        'rewrite_url': urltag_re
    }

    def input(self, _in, out, **kw):
        source_path, output_path = kw['source_path'], kw['output_path']

        # Get source and output path relative to media directory (they are
        # probably absolute paths, we need to work with them as env.url
        # based urls (e.g. the following code will consider them absolute
        # within a filesystem chrooted into env.url).
        root = addsep(self.env.directory)
        # To make common_path_prefix() work properly in all cases, make sure
        # we remove stuff like ../ from all paths.
        output_path = normpath(join(root, output_path))
        source_path = normpath(join(root, source_path))
        root = normpath(root)

        cpp = common_path_prefix
        self.output_url = path2url(output_path[len(cpp([root, output_path])):])
        self.source_url = path2url(source_path[len(cpp([root, source_path])):])

        return super(CSSUrlRewriter, self).input(_in, out, **kw)

    def rewrite_url(self, m):
        # Get the regex matches; note how we maintain the exact
        # whitespace around the actual url; we'll indeed only
        # replace the url itself.
        text_before = m.groups()[0]
        url = m.groups()[1]
        text_after = m.groups()[2]

        # Normalize the url: remove quotes
        quotes_used = ''
        if url[:1] in '"\'':
            quotes_used = url[:1]
            url = url[1:]
        if url[-1:] in '"\'':
            url = url[:-1]

        url = self.replace_url(url)

        result = 'url(%s%s%s%s%s)' % (
            text_before, quotes_used, url, quotes_used, text_after)
        return result

    def replace_url(self, url):
        """Implement this to return a replacement for each URL found."""
        raise NotImplementedError()


if __name__ == '__main__':
    for text, expect in [
        (r'  url(icon\)xyz)  ', r'url(icon\)xyz)'),
        (r'  url(icon\\)xyz)  ', r'url(icon\\)'),
        (r'  url(icon\\\)xyz)  ', r'url(icon\\\)xyz)'),
    ]:
        m = urltag_re.search(text)
        assert m.group() == expect
