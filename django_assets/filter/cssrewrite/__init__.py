import os, re, urlparse
from django.conf import settings
import urlpath

from django_assets.filter import Filter


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
    """

    name = 'cssrewrite'
    is_source_filter = True

    def apply(self, _in, out, source_path, output_path):
        # get source and output path relative to media directory (they are
        # probably absolute paths, we need to work with them as MEDIA_URL
        # based urls (e.g. the following code will consider them absolute
        # within a filesystem chrooted into MEDIA_URL).
        root = settings.MEDIA_ROOT
        if root and root[-1] != os.path.sep:
            root += os.path.sep  # so it will be matched by commonprefix()
        output_url = output_path[len(os.path.commonprefix([root, output_path])):]
        source_url = source_path[len(os.path.commonprefix([root, source_path])):]
        if os.name == 'nt':
            output_url = output_url.replace('\\', '/')
            source_url = source_url.replace('\\', '/')

        def _rewrite(m):
            # get the regex matches; note how we maintain the exact
            # whitespace around the actual url; we'll indeed only
            # replace the url itself
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

            # if path is an absolute one, keep it
            if not url.startswith('/') and not url.startswith('http://'):
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
