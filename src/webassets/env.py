from os import path
import urlparse
from itertools import chain
from bundle import Bundle


__all__ = ('Environment', 'RegisterError')


class RegisterError(Exception):
    pass


class Environment(object):
    """Owns a collection of bundles, and a set of configuration values
    which will be used when processing these bundles.
    """

    def __init__(self, directory, url, **config):
        self._named_bundles = {}
        self._anon_bundles = []

        self.directory = directory
        self.url = url
        self.config = config

        self.debug = False
        self.cache = True
        self.updater = 'timestamp'
        self.auto_create = True
        self.expire = False

    def __iter__(self):
        return chain(self._named_bundles.itervalues(), self._anon_bundles)

    def __getitem__(self, name):
        return self._named_bundles[name]

    def __len__(self):
        return len(self._named_bundles) + len(self._anon_bundles)

    def register(self, name, *args, **kwargs):
        """Register a bundle with the given name.

        There are two possible ways to call this:

          - With a single ``Bundle`` instance argument:

              register('jquery', jquery_bundle)

          - With one or multiple arguments, automatically creating a
            new bundle inline:

              register('all.js', jquery_bundle, 'common.js', output='packed.js')
        """
        if len(args) == 0:
            raise TypeError('at least two arguments are required')
        else:
            if len(args) == 1 and not kwargs and isinstance(args[0], Bundle):
                bundle = args[0]
            else:
                bundle = Bundle(*args, **kwargs)

            if name in self._named_bundles:
                if self._named_bundles[name] == bundle:
                    pass  # ignore
                else:
                    raise RegisterError('Another bundle is already registered '+
                                        'as "%s": %s' % (name, self._named_bundles[name]))
            else:
                self._named_bundles[name] = bundle
                bundle.env = self   # take ownership

            return bundle

    def add(self, *bundles):
        """Register a list of bundles with the environment, without
        naming them.

        This isn't terribly useful in most cases. It exists primarily
        because in some cases, like when loading bundles by seaching
        in templates for the use of an "assets" tag, no name is available.
        """
        for bundle in bundles:
            self._anon_bundles.append(bundle)
            bundle.env = self    # take ownership

    def get_config(self, key, default=None):
        """This is a simple configuration area provided by the asset
        env which holds additional options used by the filters.
        """
        return self.config.get(key, default)

    def set_debug(self, debug):
        self._debug = debug
    def get_debug(self):
        return self._debug
    debug = property(get_debug, set_debug)
    """Enable/disable debug mode. Possible values are:
      - ``False``       default production mode
      - ``True``        enable debug, output the source files
      - "merge"         merge the source files, but do not apply filters
    """

    def set_cache(self, enable):
        self._cache = enable
    def get_cache(self):
        return self._cache
    cache = property(get_cache, set_cache)
    """Controls the caching behavior. The cache is only available in debug
    mode, so the value will be ignored in all other cases. Possible values
    are:
      - ``False``       do not use the cache
      - ``True``        cache using default location: MEDIA_ROOT/.cache
      - custom path     use the given directory as the cache directory
    """

    def set_updater(self, updater):
        self._updater = updater
    def get_updater(self):
        return self._updater
    updater = property(get_updater, set_updater)
    """Controls when an already cached asset should be recreated. Possible
    values are:
      - ``False``       do not recreate automatically (use the management
                        command for a manual update)
      - "timestamp"     update if a source file timestamp exceeds the
                        existing file's timestamp
      - "interval"      recreate after an interval X (in seconds), specify
                        as a tuple: ("internal", 3600)
      - "always"        always recreate an every request (avoid in
                        production environments)
    """

    def set_auto_create(self, auto_create):
        self._auto_create =  auto_create
    def get_auto_create(self):
        return self._auto_create
    auto_create = property(get_auto_create, set_auto_create)
    """Even if you disable automatic rebuilding of your assets via
    ``set_updater``, when an asset is found to be not (yet) existing,
    it would normally be created. You can set this option to ``False``
    to disable the behavior, and raise an exception instead.
    """

    def set_expire(self, expire):
        self._expire = expire
    def get_expire(self):
        return self._expire
    expire = property(get_expire, set_expire)
    """If you send your assets to the client using a far future expires
    header to minimize the 304 responses your server has to send, you need
    to make sure that changed assets will be reloaded. This feature will
    help you. Possible values are:
      - ``False``       don't do anything, expires headers may cause problems
      - "querystring"   append a querystring with the assets last
                        modification timestamp:
                            asset.js?1212592199
      - "filename"      modify the assets filename to include the timestamp:
                            asset.1212592199.js
                        this may work better with certain proxies/browsers,
                        but requires you to configure your webserver to
                        rewrite those modified filenames to the originals.
                        see also: http://www.stevesouders.com/blog/2008/08/23/revving-filenames-dont-use-querystring/
    """

    def set_directory(self, directory):
        self._directory = directory
    def get_directory(self):
        return self._directory
    directory = property(get_directory, set_directory)
    """The base directory to which all paths will be relative to.
    """

    def set_url(self, url):
        self._url = url
    def get_url(self):
        return self._url
    url = property(get_url, set_url)
    """The base used to construct urls under which ``self.directory``
    should be exposed.
    """

    def absurl(self, fragment):
        """Create an absolute url based on the root url.
        """
        root = self.url
        root += root[-1:] != '/' and '/' or ''
        return urlparse.urljoin(root, fragment)

    def abspath(self, filename):
        """Create an absolute path based on the directory.
        """
        if path.isabs(filename):
            return filename
        return path.abspath(path.join(self.directory, filename))
