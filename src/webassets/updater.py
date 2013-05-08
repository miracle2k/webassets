"""The auto-rebuild system is an optional part of webassets that can be used
during development, and can also be quite convenient on small sites that don't
have the performance requirements where a rebuild-check on every request is
fatal.

This module contains classes that help determine whether a rebuild is required
for a bundle. This is more complicated than simply comparing the timestamps of
the source and output files.

First, certain filters, in particular CSS compilers like SASS, allow bundle
source files to reference additional files which the user may not have listed
in the bundle definition. The bundles support an additional ``depends``
argument that can list files that should be watched for modification.

Second, if the bundle definition itself changes, i.e., source files being added
or removed, or the list of applied filters modified, the bundle needs to be
rebuilt also. Since there is no single fixed place where bundles are defined,
simply watching the timestamp of that bundle definition file is not good enough.

To solve the latter problem, we employ an environment-specific cache of bundle
definitions.

Note that there is no ``HashUpdater``. This doesn't make sense for two reasons.
First, for a live system, it isn't fast enough. Second, for prebuilding assets,
the cache is a superior solution for getting essentially the same speed
increase as using the hash to reliably determine which bundles to skip.
"""

from webassets import six
from webassets.six.moves import map
from webassets.six.moves import zip
from webassets.exceptions import BundleError, BuildError
from webassets.utils import RegistryMetaclass


__all__ = ('get_updater', 'SKIP_CACHE',
           'TimestampUpdater', 'AlwaysUpdater',)


SKIP_CACHE = object()
"""An updater can return this value as hint that a cache, if enabled,
should probably not be used for the rebuild; This is currently used
as a return value when a bundle's dependencies have changed, which
would currently not cause a different cache key to be used.

This is marked a hint, because in the future, the bundle may be smart
enough to make this decision by itself.
"""


class BaseUpdater(six.with_metaclass(RegistryMetaclass(
    clazz=lambda: BaseUpdater, attribute='needs_rebuild',
    desc='an updater implementation'))):
    """Base updater class.

    Child classes that define an ``id`` attribute are accessible via their
    string id in the configuration.

    A single instance can be used with different environments.
    """

    def needs_rebuild(self, bundle, env):
        """Returns ``True`` if the given bundle needs to be rebuilt,
        ``False`` otherwise.
        """
        raise NotImplementedError()

    def build_done(self, bundle, env):
        """This will be called once a bundle has been successfully built.
        """


get_updater = BaseUpdater.resolve


class BundleDefUpdater(BaseUpdater):
    """Supports the bundle definition cache update check that child
    classes are usually going to want to use also.
    """

    def check_bundle_definition(self, bundle, env):
        if not env.cache:
            # If no global cache is configured, we could always
            # fall back to a memory-cache specific for the rebuild
            # process (store as env._update_cache); however,
            # whenever a bundle definition changes, it's likely that
            # a process restart will be required also, so in most cases
            # this would make no sense.
            return False

        cache_key = ('bdef', bundle.output)
        current_hash = "%s" % hash(bundle)
        cached_hash = env.cache.get(cache_key)
        # This may seem counter-intuitive, but if no cache entry is found
        # then we actually return "no update needed". This is because
        # otherwise if no cache / a dummy cache is used, then we would be
        # rebuilding every single time.
        if not cached_hash is None:
            return cached_hash != current_hash
        return False

    def needs_rebuild(self, bundle, env):
        return self.check_bundle_definition(bundle, env)

    def build_done(self, bundle, env):
        if not env.cache:
            return False
        cache_key = ('bdef', bundle.output)
        cache_value = "%s" % hash(bundle)
        env.cache.set(cache_key, cache_value)


class TimestampUpdater(BundleDefUpdater):

    id = 'timestamp'

    def check_timestamps(self, bundle, env, o_modified=None):
        from .bundle import Bundle, is_url
        from webassets.version import TimestampVersion

        if not o_modified:
            try:
                resolved_output = bundle.resolve_output(env)
            except BundleError:
                # This exception will occur when the bundle output has
                # placeholder, but a version cannot be found. If the
                # user has defined a manifest, this will just be the first
                # build. Return True to let it happen.
                # However, if no manifest is defined, raise an error,
                # because otherwise, this updater would always return True,
                # and thus not do its job at all.
                if env.manifest is None:
                    raise BuildError((
                        '%s uses a version placeholder, and you are '
                        'using "%s" versions. To use automatic '
                        'building in this configuration, you need to '
                        'define a manifest.' % (bundle, env.versions)))
                return True

            try:
                o_modified = TimestampVersion.get_timestamp(resolved_output)
            except OSError:
                # If the output file does not exist, we'll have to rebuild
                return True

       # Recurse through the bundle hierarchy. Check the timestamp of all
        # the bundle source files, as well as any additional
        # dependencies that we are supposed to watch.
        for iterator, result in (
            (lambda e: map(lambda s: s[1], bundle.resolve_contents(e)), True),
            (bundle.resolve_depends, SKIP_CACHE)
        ):
            for item in iterator(env):
                if isinstance(item, Bundle):
                    nested_result = self.check_timestamps(item, env, o_modified)
                    if nested_result:
                        return nested_result
                elif not is_url(item):
                    try:
                        s_modified = TimestampVersion.get_timestamp(item)
                    except OSError:
                        # If a file goes missing, always require
                        # a rebuild.
                        return result
                    else:
                        if s_modified > o_modified:
                            return result
        return False

    def needs_rebuild(self, bundle, env):
        return \
            super(TimestampUpdater, self).needs_rebuild(bundle, env) or \
            self.check_timestamps(bundle, env)

    def build_done(self, bundle, env):
        # Reset the resolved dependencies, so any globs will be
        # re-resolved the next time we check if a rebuild is
        # required. This ensures that we begin watching new files
        # that are created, while still caching the globs as long
        # no changes happen.
        bundle._resolved_depends = None
        super(TimestampUpdater, self).build_done(bundle, env)


class AlwaysUpdater(BaseUpdater):

    id = 'always'

    def needs_rebuild(self, bundle, env):
        return True

