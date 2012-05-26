import urlparse
from webassets.filter.cssrewrite import urlpath
from webassets.filter.cssrewrite.base import CSSUrlRewriter, addsep

try:
    from collections import OrderedDict
except ImportError:
    # Use an ordered dict when available, otherwise we simply don't
    # support ordering - it's just a nice bonus.
    OrderedDict = dict

class CSSRewriteAbsolute(CSSUrlRewriter):
    """Source filter that rewrites urls in CSS files.

    CSS allows you to specify urls relative to the location of the CSS file.
    However, you may want to store your compressed assets in a different place
    than source files, or merge source files from different locations. This
    would then break these CSS references, since the base URL changed.

    This filter rewrites CSS ``url()`` instructions in the source
    files to replace them exactly how you want it. It works as
    a *source filter*, i.e. it is applied individually to each source file
    before they are merged.

        if debug:
            bundle = Bundle(
                path.join('css', 'html5boilerplate.css'),
                path.join('leaflet','dist', 'leaflet.css'),
                output=path.join('..', 'static', 'css', 'lib.css'),
                filters=(CSSRewriteAbsolute(replace={'images/':'/images/'}),)
            )
        else:
            bundle = Bundle(
                path.join('css', 'html5boilerplate.css'),
                path.join('leaflet','dist', 'leaflet.css'),
                output=path.join('..', 'static', 'css', 'lib.css'),
                filters=('cssmin',CSSRewriteAbsolute(replace={'images/':'/images/'}))
            )

    This will rewrite all urls that point to files within the relative path
    ``images`` to the absolute path ``/images/`` as a prefix instead.
    """


    name = 'cssrewrite_absolute'

    def __init__(self, replace=False):
        super(CSSRewriteAbsolute, self).__init__()
        self.replace = replace

    def unique(self):
        # Allow mixing the standard version of this filter, and replace mode.
        return self.replace

    def input(self, _in, out, **kw):
        replace_dict = False
        root = addsep(self.env.directory)
        if self.replace not in (False, None):
            replace_dict = OrderedDict()
            for repldir, sub in self.replace.items():
                replace_dict[repldir] = sub
            self.replace_dict = replace_dict

        return super(CSSRewriteAbsolute, self).input(_in, out, **kw)

    def replace_url(self, url):
        # Replace mode: manually adjust the location of files
        if self.replace is not False:
            for to_replace, sub in self.replace_dict.items():
                if url.startswith(to_replace):
                    url = "%s%s" % (sub, url[len(to_replace):])
                    # Only apply the first match
                    break

        # Default mode: auto correct relative urls
        else:
            url = urlpath.relpath(self.output_url,
                urlparse.urljoin(self.source_url, url))

        return url