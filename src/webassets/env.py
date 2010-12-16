from os import path
import urlparse
from itertools import chain
from bundle import Bundle


__all__ = ('Environment', 'RegisterError')


class RegisterError(Exception):
    pass


class ConfigStorage(object):
    """This is the backend which :class:`Environment` uses to store
    it's configuration values.

    Environment-subclasses like the one used by ``django-assets`` will
    often want to use a custom ``ConfigStorage`` as well, building upon
    whatever configuration the framework is using.

    The goal in designing this class therefore is to make it easy for
    subclasses to change the place the data is stored: Only
    _meth:`__getitem__`, _meth:`__setitem__`, _meth:`__delitem__` and
    _meth:`__contains__` need to be implemented.

    One rule: The default storage is case-insensitive, and custom
    environments should maintain those semantics.

    A related reason is why we don't inherit from ``dict``. It would
    require us to re-implement a whole bunch of methods, like pop() etc.
    """

    def __init__(self, env):
        self.env = env

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def update(self, d):
        for key in d:
            self.__setitem__(key, d[key])

    def setdefault(self, key, value):
        if not key in self:
            self.__setitem__(key, value)
            return value
        return self.__getitem__(key)

    def __contains__(self, key):
        raise NotImplementedError()

    def __getitem__(self, key):
        raise NotImplementedError()

    def __setitem__(self, key, value):
        raise NotImplementedError()

    def __delitem__(self, key):
        raise NotImplementedError()


class BaseEnvironment(object):
    """Abstract base class for :class:`Environment` which makes
    subclassing easier.
    """

    config_storage_class = None

    def __init__(self, **config):
        self._named_bundles = {}
        self._anon_bundles = []
        self._config = self.config_storage_class(self)

        # directory, url currently do not have default values
        self.config.setdefault('debug', False)
        self.config.setdefault('cache', True)
        self.config.setdefault('updater', 'timestamp')
        self.config.setdefault('expire', 'querystring')

        self.config.update(config)

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

    @property
    def config(self):
        """Key-value configuration. Keys are case-insensitive.
        """
        # This is a property so that user are not tempted to assign
        # a custom dictionary which won't uphold our caseless semantics.
        return self._config

    def set_debug(self, debug):
        self.config['debug'] = debug
    def get_debug(self):
        return self.config['debug']
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
        self.config['cache'] = enable
    def get_cache(self):
        return self.config['cache']
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
        self.config['updater'] = updater
    def get_updater(self):
        return self.config['updater']
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
        self.config['expire'] = expire
    def get_expire(self):
        return self.config['expire']
    expire = property(get_expire, set_expire, doc=
    """If you send your assets to the client using a *far future expires*
    header (to minimize the 304 responses your server has to send), you
    need to make sure that changed assets will be reloaded when they change.

    This feature will help. Possible values are:

      ``False``
          Don't do anything.

      ``"querystring"`` (default)
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
        self.config['directory'] = directory
    def get_directory(self):
        return self.config['directory']
    directory = property(get_directory, set_directory, doc=
    """The base directory to which all paths will be relative to.
    """)

    def set_url(self, url):
        self.config['url'] = url
    def get_url(self):
        return self.config['url']
    url = property(get_url, set_url, doc=
    """The base used to construct urls under which :attr:`directory`
    should be exposed.
    """)

    def absurl(self, fragment):
        """Create an absolute url based on the root url.

        TODO: Not sure if it feels right that these are environment
        methods, rather than global helpers.
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


class DictConfigStorage(ConfigStorage):
    """Using a lower-case dict for configuration values.
    """
    def __init__(self, *a, **kw):
        self._dict = {}
        ConfigStorage.__init__(self, *a, **kw)
    def __contains__(self, key):
        return self._dict.__contains__(key.lower())
    def __getitem__(self, key):
        return self._dict.__getitem__(key.lower())
    def __setitem__(self, key, value):
        self._dict.__setitem__(key.lower(), value)
    def __delitem__(self, key):
        self._dict.__delitem__(key.lower())


class Environment(BaseEnvironment):
    """Owns a collection of bundles, and a set of configuration values
    which will be used when processing these bundles.
    """

    config_storage_class = DictConfigStorage

    def __init__(self, directory, url, **more_config):
        super(Environment, self).__init__(**more_config)
        self.directory = directory
        self.url = url