import os, re, urlparse
from os.path import join, commonprefix, normpath
import urlpath
try:
    from collections import OrderedDict
except ImportError:
    # Use an ordered dict when available, otherwise we simply don't
    # support ordering - it's just a nice bonus.
    OrderedDict = dict

from webassets.filter import Filter


__all__ = ('CSSRewriteFilter',)


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


class CSSRewriteFilter(Filter):
    """Source filter that rewrites relative urls in CSS files.

    CSS allows you to specify urls relative to the location of the CSS
    file. However, you may want to store your compressed assets in a
    different place than source files, or merge source files from
    different locations. This would then break these relative CSS
    references, since the base URL changed.

    This filter transparently rewrites CSS ``url()`` instructions
    in the source files to make them relative to the location of the
    output path. It works as a *source filter*, i.e. it is applied
    individually to each source file before they are merged.

    No configuration is necessary.

    The filter also supports a manual mode::

        get_filter('cssrewrite', replace={'old_directory', '/custom/path/'})

    This will rewrite all urls that point to files within ``old_directory``
    to use ``/custom/path`` as a prefix instead.
    """

    # TODO: If we want to support inline assets, this needs to be
    # updated to optionally convert URLs to absolute ones based on
    # MEDIA_URL.

    name = 'cssrewrite'

    def __init__(self, replace=False):
        super(CSSRewriteFilter, self).__init__()
        self.replace = replace

    def unique(self):
        # Allow mixing the standard version of this filter, and the
        # replace mode.
        return self.replace

    def input(self, _in, out, source_path, output_path):
        # Get source and output path relative to media directory (they are
        # probably absolute paths, we need to work with them as env.url
        # based urls (e.g. the following code will consider them absolute
        # within a filesystem chrooted into env.url).
        root = addsep(self.env.directory)
        # To make commonprefix() work properly in all cases, make sure we
        # remove stuff like ../ from all paths.
        output_path = normpath(join(root, output_path))
        source_path = normpath(join(root, source_path))
        root = normpath(root)

        output_url = path2url(output_path[len(commonprefix([root, output_path])):])
        source_url = path2url(source_path[len(commonprefix([root, source_path])):])

        # For replace mode, make sure we have all the directories to be
        # rewritten in form of a url, so we can later easily match it
        # against the urls encountered in the CSS.
        replace = False
        if self.replace not in (False, None):
            replace = OrderedDict()
            for repldir, sub in self.replace.items():
                repldir = addsep(os.path.normpath(join(root, repldir)))
                replurl = path2url(repldir[len(commonprefix([root, repldir])):])
                replace[replurl] = sub

        def _rewrite(m):
            # Get the regex matches; note how we maintain the exact
            # whitespace around the actual url; we'll indeed only
            # replace the url itself.
            text_before = m.groups()[0]
            url = m.groups()[1]
            text_after = m.groups()[2]

            # normalize the url we got
            quotes_used = ''
            if url[:1] in '"\'':
                quotes_used = url[:1]
                url = url[1:]
            if url[-1:] in '"\'':
                url = url[:-1]

            # Replace mode: manually adjust the location of files
            if replace is not False:
                for to_replace, sub in replace.items():
                    targeturl = urlparse.urljoin(source_url, url)
                    if targeturl.startswith(to_replace):
                        url = "%s%s" % (sub, targeturl[len(to_replace):])
                        # Only apply the first match
                        break

            # Default mode: auto correct relative urls
            else:
                # If path is an absolute one, keep it
                if not url.startswith('/') and not (url.startswith('http://') or url.startswith('https://')):
                    # rewritten url: relative path from new location (output)
                    # to location of referenced file (source + current url)
                    url = urlpath.relpath(output_url,
                                          urlparse.urljoin(source_url, url))

            result = 'url(%s%s%s%s%s)' % (
                        text_before, quotes_used, url, quotes_used, text_after)
            return result

        out.write(urltag_re.sub(_rewrite, _in.read()))


if __name__ == '__main__':
    for text, expect in [
            (r'  url(icon\)xyz)  ', r'url(icon\)xyz)'),
            (r'  url(icon\\)xyz)  ', r'url(icon\\)'),
            (r'  url(icon\\\)xyz)  ', r'url(icon\\\)xyz)'),
        ]:
        m = urltag_re.search(text)
        assert m.group() == expect
