import os, urlparse
from os.path import join
from webassets.utils import common_path_prefix
from webassets.external import ExternalAssets
import urlpath
try:
    from collections import OrderedDict
except ImportError:
    # Use an ordered dict when available, otherwise we simply don't
    # support ordering - it's just a nice bonus.
    OrderedDict = dict

from base import CSSUrlRewriter, addsep, path2url


__all__ = ('CSSRewrite',)


class CSSRewrite(CSSUrlRewriter):
    """Source filter that rewrites relative urls in CSS files.

    CSS allows you to specify urls relative to the location of the CSS file.
    However, you may want to store your compressed assets in a different place
    than source files, or merge source files from different locations. This
    would then break these relative CSS references, since the base URL changed.

    This filter transparently rewrites CSS ``url()`` instructions in the source
    files to make them relative to the location of the output path. It works as
    a *source filter*, i.e. it is applied individually to each source file
    before they are merged.

    No configuration is necessary.

    The filter also supports a manual mode, using either ``replace`` or ``external``::

        get_filter('cssrewrite', replace={'old_directory':'/custom/path/'})

    This will rewrite all urls that point to files within ``old_directory`` to
    use ``/custom/path`` as a prefix instead.

    You may plug in your own replace function::

        get_filter('cssrewrite', replace=lambda url: re.sub(r'^/?images/', '/images/', url))
        get_filter('cssrewrite', replace=lambda url: '/images/'+url[7:] if url.startswith('images/') else url)
    """

    # TODO: If we want to support inline assets, this needs to be
    # updated to optionally convert URLs to absolute ones based on
    # MEDIA_URL.

    name = 'cssrewrite'
    max_debug_level = 'merge'

    def __init__(self, replace=False):
        super(CSSRewrite, self).__init__()
        self.replace = replace
        self.external = []

    def unique(self):
        # Allow mixing the standard version of this filter, and replace mode.
        return self.replace

    def input(self, _in, out, **kw):
        if self.replace not in (False, None) and not callable(self.replace):
            # For replace mode, make sure we have all the directories to be
            # rewritten in form of a url, so we can later easily match it
            # against the urls encountered in the CSS.
            replace_dict = False
            root = addsep(self.env.directory)
            replace_dict = OrderedDict()
            for repldir, sub in self.replace.items():
                repldir = addsep(os.path.normpath(join(root, repldir)))
                replurl = path2url(repldir[len(common_path_prefix([root, repldir])):])
                replace_dict[replurl] = sub
            self.replace_dict = replace_dict

        # see if we have external assets in the environment
        for bundle in self.env:
            if isinstance(bundle, ExternalAssets):
                self.external.append(bundle)
            #pass

        return super(CSSRewrite, self).input(_in, out, **kw)

    def _is_abs_url(self, url):
        return url.startswith('/') and (url.startswith('http://') or url.startswith('https://'))

    def replace_url(self, url):
        # Replace mode: manually adjust the location of files
        if callable(self.replace):
            return self.replace(url)
        elif self.replace is not False:
            for to_replace, sub in self.replace_dict.items():
                targeturl = urlparse.urljoin(self.source_url, url)
                if targeturl.startswith(to_replace):
                    url = "%s%s" % (sub, targeturl[len(to_replace):])
                    # Only apply the first match
                    break

        else:
            # External mode: use ExternalAssets objects
            # to fetch replacements
            if len(self.external):
                # If path is an absolute one, keep it
                if not self._is_abs_url(url):

                    replacement = None

                    file_path = urlpath.pathjoin(self.source_path, url)
                    asset_path = None
                    for external_assets in self.external:
                        # see if our file has a versioned version available
                        try:
                            asset_path = external_assets.versioned_folder(file_path)
                            break
                        except IOError:
                            pass

                    if asset_path is not None:
                        if self.env.url:
                            # see if it's a complete url (rather than a folder)
                            # otherwise we want a relative path in the CSS
                            if self.env.url.startswith('http://')\
                                or self.env.url.startswith('https://')\
                                or self.env.url.startswith('//'):
                                replacement = urlparse.urljoin(self.env.url, asset_path)
                            else:
                                abs_asset_path = os.path.join(self.env.directory, asset_path)
                                replacement = urlpath.relpathto(self.env.directory, self.output_path, abs_asset_path)
                        else:
                            replacement = urlpath.relpathto(self.env.directory, self.output_path, asset_path)

                    if replacement is None:
                        url = urlpath.relpath(self.output_url,
                            urlparse.urljoin(self.source_url, url))
                    else:
                        url = replacement

            else:
                # Default mode: auto correct relative urls
                # If path is an absolute one, keep it
                if not self._is_abs_url(url):
                    # rewritten url: relative path from new location (output)
                    # to location of referenced file (source + current url)
                    url = urlpath.relpath(self.output_url,
                        urlparse.urljoin(self.source_url, url))

        return url
