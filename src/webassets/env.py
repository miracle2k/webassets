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
    debug = property(get_debug, set_debug, doc=
    """Enable/disable debug mode. Possible values are:

        ``False``
            Production mode. Bundles will be merged and filters applied.
        ``True``
            Enable debug mode. Bundles will output their individual source
            files.
        *"merge"*
            Merge the source files, but do not apply filters.
    """)

    def set_cache(self, enable):
        self._cache = enable
    def get_cache(self):
        return self._cache
    cache = property(get_cache, set_cache, doc=
    """Controls the behavior of the cache. The cache will speed up rebuilding
    of your bundles, by caching individual filter results. This can be
    particulary useful while developing, if your bundles would otherwise take
    a long time to rebuild.

    Possible values are:

      ``False``
          Do not use the cache.

      ``True`` (default)
          Cache using default location, a ``.cache`` folder inside
          :attr:`directory`.

      *custom path*
         Use the given directory as the cache directory.

    Note: Currently, the cache is never used while in production mode.
    """)

    def set_updater(self, updater):
        self._updater = updater
    def get_updater(self):
        return self._updater
    updater = property(get_updater, set_updater, doc=
    """Controls when and if bundles should be automatically rebuilt.
    Possible values are:

      ``False``
          Do not auto-rebuilt bundles. You will need to use the command
          line interface to update bundles yourself. Note that the with
          this settings, bundles will not only be not rebuilt, but will
          not be automatically built at all, period (even the initial
          build needs to be done manually).

      ``"timestamp"`` (default)
          Rebuild bundles if the source file timestamp exceeds the existing
          output file's timestamp.

      ``"interval"``
          Always rebuild after an interval of X seconds has passed.
          Specify as a tuple: ``("internal", 3600)``.

      ``"always"``
          Always rebuild bundles (avoid in production environments).

    For most people, the default value will make a lot of sense. However,
    if you want to avoid the request which causes a rebuild taking too
    long, you may want to disable auto-rebuilds and instead rebuild
    yourself, outside of your webserver process.
    """)

    def set_expire(self, expire):
        self._expire = expire
    def get_expire(self):
        return self._expire
    expire = property(get_expire, set_expire, doc=
    """If you send your assets to the client using a *far future expires*
    header (to minimize the 304 responses your server has to send), you
    need to make sure that changed assets will be reloaded when they change.

    This feature will help. Possible values are:

      ``False``
          Don't do anything.

      ``"querystring"``
          Append a querystring with a timestamp to generated urls, e.g.
          ``asset.js?1212592199``.

      ``"filename"``
          Modify the filename to include a timestamp, e.g.
          ``asset.1212592199.js``. This may work better with certain
          proxies, but requires you to configure your webserver to
          rewrite those modified filenames to the originals. See also
          `High Performance Web Sites blog <http://www.stevesouders.com/blog/2008/08/23/revving-filenames-dont-use-querystring/>`_.
    """)

    def set_directory(self, directory):
        self._directory = directory
    def get_directory(self):
        return self._directory
    directory = property(get_directory, set_directory, doc=
    """The base directory to which all paths will be relative to.
    """)

    def set_url(self, url):
        self._url = url
    def get_url(self):
        return self._url
    url = property(get_url, set_url, doc=
    """The base used to construct urls under which :attr:`directory`
    should be exposed.
    """)

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
