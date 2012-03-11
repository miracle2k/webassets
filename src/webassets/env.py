from os import path
import urlparse
from itertools import chain
import warnings
from bundle import Bundle
from cache import get_cache
from version import get_versioner, get_manifest
from updater import get_updater
from exceptions import ImminentDeprecationWarning


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

    def _get_deprecated(self, key):
        """For deprecated keys, fake the values as good as we can.
        Subclasses need to call this in __getitem__."""
        self._warn_key_deprecation(key)
        if key == 'expire':
            return 'querystring' if self['url_expire'] else False

    def _set_deprecated(self, key, value):
        self._warn_key_deprecation(key)
        if key == 'expire':
            if value == 'filename':
                raise DeprecationWarning(
                    ('The "expire" option has been deprecated. Instead '
                     'of the "filesystem" expiry mode, use the %(version)s '
                     'placeholder in your bundle\'s output filename.'))
            self['url_expire'] = bool(value)
            return True
        if key == 'updater':
            if not value or value == 'never':
                self['auto_build'] = False
                warnings.warn((
                    'The "updater" option no longer can be set to False '
                    'or "never" to disable automatic building. Instead, '
                    'use the new "auto_build" boolean option.'),
                        ImminentDeprecationWarning)
                return True

    def _warn_key_deprecation(self, key):
        """Subclasses should override this to provide custom
        warnings with their mapped keys in the error message."""
        import warnings
        if  key == 'expire':
            warnings.warn((
                'The "expire" option has been deprecated in 0.7, and '
                'replaced with a boolean option "url_expire". If you '
                'want to append something other than a timestamp to '
                'your URLs, check out the "versions" option.'),
                    ImminentDeprecationWarning)


# Those are config keys used by the environment. Framework-wrappers may
# find this list useful if they desire to prefix those settings. For example,
# in Django, it would be ASSETS_DEBUG. Other config keys are encouraged to use
# their own namespacing, so they don't need to be prefixed. For example, a
# filter setting might be CSSMIN_BIN.
env_options = [
    'directory', 'url', 'debug', 'cache', 'updater', 'auto_build',
    'url_expire', 'versions', 'manifest']


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
        #
        # some thought went into these defaults:
        #   - enable url_expire, because we want to encourage the right thing
        #   - default to hash versions, for the same reason: they're better
        #   - manifest=cache because hash versions are slow
        self.config.setdefault('debug', False)
        self.config.setdefault('cache', True)
        self.config.setdefault('url_expire', None)
        self.config.setdefault('auto_build', True)
        self.config.setdefault('manifest', 'cache')
        self.config.setdefault('versions', 'hash')
        self.config.setdefault('updater', 'timestamp')

        self.config.update(config)

    def __iter__(self):
        return chain(self._named_bundles.itervalues(), self._anon_bundles)

    def __getitem__(self, name):
        return self._named_bundles[name]

    def __contains__(self, name):
        return name in self._named_bundles

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

    def _set_debug(self, debug):
        self.config['debug'] = debug
    def _get_debug(self):
        return self.config['debug']
    debug = property(_get_debug, _set_debug, doc=
    """Enable/disable debug mode. Possible values are:

        ``False``
            Production mode. Bundles will be merged and filters applied.
        ``True``
            Enable debug mode. Bundles will output their individual source
            files.
        *"merge"*
            Merge the source files, but do not apply filters.
    """)

    def _set_cache(self, enable):
        self.config['cache'] = enable
    def _get_cache(self):
        cache = get_cache(self.config['cache'], self)
        if cache != self.config['cache']:
            self.config['cache'] = cache
        return cache
    cache = property(_get_cache, _set_cache, doc=
    """Controls the behavior of the cache. The cache will speed up rebuilding
    of your bundles, by caching individual filter results. This can be
    particularly useful while developing, if your bundles would otherwise take
    a long time to rebuild.

    Possible values are:

      ``False``
          Do not use the cache.

      ``True`` (default)
          Cache using default location, a ``.webassets-cache`` folder inside
          :attr:`directory`.

      *custom path*
         Use the given directory as the cache directory.
    """)

    def _set_auto_build(self, value):
        self.config['auto_build'] = value
    def _get_auto_build(self):
        return self.config['auto_build']
    auto_build = property(_get_auto_build, _set_auto_build, doc=
    """Controls whether bundles should be automatically built, and
    rebuilt, when required (if set to ``True``), or whether they
    must be built manually be the user, for example via a management
    command.

    This is a good setting to have enabled during debugging, and can
    be very convenient for low-traffic sites in production as well.
    However, there is a cost in checking whether the source files
    have changed, so if you care about performance, or if your build
    process takes very long, then you may want to disable this.

    By default automatic building is enabled.
    """)

    def _set_manifest(self, manifest):
        self.config['manifest'] = manifest
    def _get_manifest(self):
        manifest = get_manifest(self.config['manifest'], env=self)
        if manifest != self.config['manifest']:
            self.config['manifest'] = manifest
        return manifest
    manifest = property(_get_manifest, _set_manifest, doc=
    """A manifest persists information about the versions bundles
    are at.

    The Manifest plays a role only if you insert the bundle version
    in your output filenames, or append the version as a querystring
    to the url (via the ``url_expire`` option). It serves two
    purposes:

        - Without a manifest, it may be impossible to determine the
          version at runtime. In a deployed app, the media files may
          be stored on a different server entirely, and be
          inaccessible from the application code. The manifest,
          if shipped with your application, is what still allows to
          construct the proper URLs.

        - Even if it were possible to determine the version at
          runtime without a manifest, it may be a costly process,
          and using a manifest may give you better performance. If
          you use a hash-based version for example, this hash would
          need to be recalculated every time a new process is
          started.

    Valid values are:

      ``"cache"`` (default)
          The cache is used to remember version information. This
          is useful to avoid recalculating the version hash.

      ``"file:{path}"``
          Stores version information in a file at {path}. If not
          path is given, the manifest will be stored as
          ``.webassets-manifest`` in ``Environment.directory``.

      ``False``, ``None``
          No manifest is used.

      Any custom manifest implementation.

    The default value is ``None``.
    """)

    def _set_versions(self, versions):
        self.config['versions'] = versions
    def _get_versions(self):
        versions = get_versioner(self.config['versions'])
        if versions != self.config['versions']:
            self.config['versions'] = versions
        return versions
    versions = property(_get_versions, _set_versions, doc=
    """Defines what should be used as a Bundle ``version``.

    A bundle's version is what is appended to URLs when the
    ``url_expire`` option is enabled, and the version can be part
    of a Bundle's output filename by use of the ``%(version)s``
    placeholder.

    Valid values are:

      ``timestamp``
          The version is determined by looking at the mtime of a
          bundle's output file.

      ``hash`` (default)
          The version is a hash over the output file's content.

      ``False``, ``None``
          Functionality that requires a version is disabled. This
          includes the ``url_expire`` option, the ``auto_build``
          option, and support for the %(version)s placeholder.

      Any custom version implementation.

    The default value is ``timestamp``. Along with ``hash``, one
    of these two values are going to be what most users are looking
    for.
    """)

    def set_updater(self, updater):
        self.config['updater'] = updater
    def get_updater(self):
        value = self.config['updater']
        updater = get_updater(self.config['updater'])
        if updater != self.config['updater']:
            self.config['updater'] = updater
        return updater
    updater = property(get_updater, set_updater, doc=
    """Controls how the ``auto_build`` option should determine
    whether a bundle needs to be rebuilt.

      ``"timestamp"`` (default)
          Rebuild bundles if the source file timestamp exceeds the existing
          output file's timestamp.

      ``"always"``
          Always rebuild bundles (avoid in production environments).

      Any custom version implementation.
    """)

    def _set_url_expire(self, url_expire):
        self.config['url_expire'] = url_expire
    def _get_url_expire(self):
        return self.config['url_expire']
    url_expire = property(_get_url_expire, _set_url_expire, doc=
    """If you send your assets to the client using a
    *far future expires* header (to minimize the 304 responses
    your server has to send), you need to make sure that assets
    will be reloaded by the browser when they change.

    If this is set to ``True``, then the Bundle URLs generated by
    webassets will have their version (see ``Environment.versions``)
    appended as a querystring.

    An alternative approach would be to use the ``%(version)s``
    placeholder in the bundle output file.

    The default behavior (indicated by a ``None`` value) is to add
    an expiry querystring if the bundle does not use a version
    placeholder.
    """)

    def _set_directory(self, directory):
        self.config['directory'] = directory
    def _get_directory(self):
        return self.config['directory']
    directory = property(_get_directory, _set_directory, doc=
    """The base directory to which all paths will be relative to.
    """)

    def _set_url(self, url):
        self.config['url'] = url
    def _get_url(self):
        return self.config['url']
    url = property(_get_url, _set_url, doc=
    """The base used to construct urls under which :attr:`directory`
    should be exposed.
    """)

    # Deprecated attributes, remove in 0.8?; warnings are raised by
    # the config backend.
    def _set_expire(self, expire):
        self.config['expire'] = expire
    def _get_expire(self):
        return self.config['expire']
    expire = property(_get_expire, _set_expire)

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

    def _normalize_source_path(self, spath):
        """Called once for every source item processed by a Bundle.

        It is supposed to return the absolute path to the file, or
        raise an exception. It is primarily intended as a hook for
        third party integration libraries to provide support for
        virtual paths (like Flask Blueprints, or Django staticfiles).

        The function is not called for urls. It is also currently
        not called for paths that use glob patterns, meaning those
        cannot be virtualized at this point (TODO: See if we can
        do something about this).
        """
        spath = self.abspath(spath)
        if not path.exists(spath):
            raise IOError("'%s' does not exist" % spath)
        return spath


class DictConfigStorage(ConfigStorage):
    """Using a lower-case dict for configuration values.
    """
    def __init__(self, *a, **kw):
        self._dict = {}
        ConfigStorage.__init__(self, *a, **kw)
    def __contains__(self, key):
        return self._dict.__contains__(key.lower())
    def __getitem__(self, key):
        key = key.lower()
        value = self._get_deprecated(key)
        if not value is None:
            return value
        return self._dict.__getitem__(key)
    def __setitem__(self, key, value):
        key = key.lower()
        if not self._set_deprecated(key, value):
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
