import os
from os import path
import urlparse
import os

try:
    # Current version of glob2 does not let us access has_magic :/
    import glob2 as glob
    from glob import has_magic
except ImportError:
    import glob
    from glob import has_magic
import warnings
from filter import get_filter
from merge import (FileHunk, UrlHunk, FilterTool, merge, merge_filters,
                  MoreThanOneFilterError)
from updater import SKIP_CACHE
from exceptions import BundleError, BuildError


__all__ = ('Bundle', 'get_all_bundle_files',)


def is_url(s):
    if not isinstance(s, str):
        return False
    scheme = urlparse.urlsplit(s).scheme
    return bool(scheme) and len(scheme) > 1


def has_placeholder(s):
    return '%(version)s' in s


class Bundle(object):
    """A bundle is the unit webassets uses to organize groups of
    media files, which filters to apply and where to store them.

    Bundles can be nested arbitrarily.

    A note on the connection between a bundle and an "environment"
    instance: The bundle requires a environment that it belongs to.
    Without an environment, it lacks information about how to behave,
    and cannot know where relative paths are actually based.
    However, I don't want to make the Bundle.__init__ syntax more
    complicated than it already is by requiring an Environment object
    to be passed. This would be a particular nuisance when nested
    bundles are used. Further, nested bundles are never explicitly
    connected to an Environment, and what's more, the same child
    bundle can be used in multiple parent bundles.

    This is the reason why basically every method of the Bundle
    class takes an ``env`` parameter - so a parent bundle can provide
    the environment for child bundles that do not know it.
    """

    def __init__(self, *contents, **options):
        self.env = None
        self.contents = contents
        self.output = options.pop('output', None)
        self.filters = options.pop('filters', None)
        self.debug = options.pop('debug', None)
        self.depends = options.pop('depends', [])
        self.version = options.pop('version', [])
        if options:
            raise TypeError("got unexpected keyword argument '%s'" %
                            options.keys()[0])
        self.extra_data = {}

    def __repr__(self):
        return "<%s output=%s, filters=%s, contents=%s>" % (
            self.__class__.__name__,
            self.output,
            self.filters,
            self.contents,
        )

    def _get_filters(self):
        return self._filters
    def _set_filters(self, value):
        """Filters may be specified in a variety of different ways,
        including by giving their name; we need to make sure we resolve
        everything to an actual filter instance.
        """
        if value is None:
            self._filters = ()
            return

        if isinstance(value, basestring):
            filters = map(unicode.strip, unicode(value).split(','))
        elif isinstance(value, (list, tuple)):
            filters = value
        else:
            filters = [value]
        self._filters = [get_filter(f) for f in filters]
    filters = property(_get_filters, _set_filters)

    def _get_contents(self):
        return self._contents
    def _set_contents(self, value):
        self._contents = value
        self._resolved_contents = None
    contents = property(_get_contents, _set_contents)

    def resolve_contents(self, env=None, force=False):
        """Convert bundle contents into something that can be easily processed.

        - Glob patterns are resolved
        - Validate all the source paths to complain about missing files early.
        - Third party extensions get to hook into this to provide a basic
          virtualized filesystem.

        The return value is a list of 2-tuples (relpath, abspath). The first
        element is the path that is assumed to be relative to the
        ``Environment.directory`` value. We need it to construct urls to the
        source files.
        The second element is the absolute path to the actual location of the
        file. Depending on the magic a third party extension does, this may be
        somewhere completely different.

        URLs and nested Bundles are returned as a 2-tuple where both items are
        the same.

        Set ``force`` to ignore any cache, and always re-resolve glob patterns.
        """
        env = self._get_env(env)

        # TODO: We cache the values, which in theory is problematic, since
        # due to changes in the env object, the result of the globbing may
        # change. Not to mention that a different env object may be passed
        # in. We should find a fix for this.
        if getattr(self, '_resolved_contents', None) is None or force:
            l = []
            for item in self.contents:
                if isinstance(item, Bundle):
                    l.append((item, item))
                else:
                    if is_url(item):
                        # Is a URL
                        l.append((item, item))
                    elif isinstance(item, basestring) and has_magic(item):
                        # Is globbed pattern
                        path = env.abspath(item)
                        for f in glob.glob(path):
                            if os.path.isdir(f):
                                continue
                            if self.output and env.abspath(self.output) == f:
                                # Exclude the output file. Note this will
                                # not work if nested bundles do the
                                # including. TODO: Should be even have this
                                # test if it doesn't work properly? Should
                                # be throw an error during building instead?
                                # Or can be give this method access to the
                                # parent bundle, since allowing env settings
                                # overrides in bundles is planned anyway?
                                continue
                            l.append((f[len(path)-len(item):], f))
                    else:
                        # Is just a normal path; Send it through
                        # _normalize_source_path().
                        try:
                            l.append((item, env._normalize_source_path(item)))
                        except IOError, e:
                            raise BundleError(e)
            self._resolved_contents = l
        return self._resolved_contents

    def _get_depends(self):
        return self._depends
    def _set_depends(self, value):
        self._depends = [value] if isinstance(value, basestring) else value
        self._resolved_depends = None
    depends = property(_get_depends, _set_depends, doc=
    """Allows you to define an additional set of files (glob syntax
    is supported), which are considered when determining whether a
    rebuild is required.
    """)

    def resolve_depends(self, env):
        # TODO: Caching is as problematic here as it is in resolve_contents().
        if not self.depends:
            return []
        if getattr(self, '_resolved_depends', None) is None:
            l = []
            for item in self.depends:
                if has_magic(item):
                    dir = env.abspath(item)
                    for f in glob.glob(dir):
                        l.append(f)
                else:
                    try:
                        l.append(env._normalize_source_path(item))
                    except IOError, e:
                        raise BundleError(e)
            self._resolved_depends = l
        return self._resolved_depends

    def get_version(self, env=None, refresh=False):
        """Return the current version of the Bundle.

        If the version is not cached in memory, it will first look in the
        manifest, then ask the versioner.

        ``refresh`` causes a value in memory to be ignored, and the version
        to be looked up anew.
        """
        env = self._get_env(env)
        if not self.version or refresh:
            version = None
            # First, try a manifest. This should be the fastest way.
            if env.manifest:
                version = env.manifest.query(self, env)
            # Often the versioner is able to help.
            if not version:
                from version import VersionIndeterminableError
                if env.versions:
                    try:
                        version = env.versions.determine_version(self, env)
                        assert version
                    except VersionIndeterminableError, e:
                        reason = e
                else:
                    reason = '"versions" option not set'
            if not version:
                raise BundleError((
                    'Cannot find version of %s. There is no manifest '
                    'which knows the version, and it cannot be '
                    'determined dynamically, because: %s') % (self, reason))
            self.version = version
        return self.version

    def resolve_output(self, env=None, version=None, rel=False):
        """Return the full, absolute output path.

        If a %(version)s placeholder is used, it is replaced.
        """
        env = self._get_env(env)
        output = self.output
        if has_placeholder(output):
            output = output % {'version': version or self.get_version(env)}
        if rel:
            return output
        return env.abspath(output)

    def __hash__(self):
        """This is used to determine when a bundle definition has
        changed so that a rebuild is required.

        The hash therefore should be built upon data that actually
        affect the final build result.
        """
        return hash((tuple(self.contents),
                     self.output,
                     tuple(self.filters),
                     self.debug))
        # Note how self.depends is not included here. It could be,
        # but we really want this hash to only change for stuff
        # that affects the actual output bytes. Note that modifying
        # depends will be effective after the first rebuild in any
        # case.

    @property
    def is_container(self):
        """Return true if this is a container bundle, that is, a bundle
        that acts only as a container for a number of sub-bundles.

        It must not contain any files of it's own, and must have an
        empty ``output`` attribute.
        """
        has_files = any([c for c in self.contents if not isinstance(c, Bundle)])
        return not has_files and not self.output

    def _get_env(self, env):
        # Note how bool(env) can be False, due to __len__.
        env = env if env is not None else self.env
        if env is None:
            raise BundleError('Bundle is not connected to an environment')
        return env

    def _merge_and_apply(self, env, output, force, parent_debug=None,
                         parent_filters=[], extra_filters=[],
                         disable_cache=None):
        """Internal recursive build method.

        ``parent_debug`` is the debug setting used by the parent bundle.
        This is not necessarily ``bundle.debug``, but rather what the
        calling method in the recursion tree is actually using.

        ``parent_filters`` are what the parent passes along, for
        us to be applied as input filters. Like ``parent_debug``, it is
        a collection of the filters of all parents in the hierarchy.

        ``extra_filters`` may exist if the parent is a container bundle
        passing filters along to it's children; these are applied as input
        and output filters (since there is no parent who could do the
        latter), and they are not passed further down the hierarchy
        (but instead they become part of ``parent_filters``.

        ``disable_cache`` is necessary because in some cases, when an
        external bundle dependency has changed, we must not rely on the
        cache, since the cache key is not taking into account changes
        in those dependencies (for now).
        """

        assert not path.isabs(output)

        # Determine the debug option to work, which will tell us what
        # building the bundle entails. The reduce chooses the first
        # non-None value.
        debug = reduce(lambda x, y: x if not x is None else y,
            [self.debug, parent_debug, env.debug])
        if debug == 'merge':
            no_filters = True
        elif debug is True:
            # This should be caught by urls().
            if any([self.debug, parent_debug]):
                raise BuildError("a bundle with debug=True cannot be built")
            else:
                raise BuildError("cannot build while in debug mode")
        elif debug is False:
            no_filters = False
        else:
            raise BundleError('Invalid debug value: %s' % debug)

        # Prepare contents
        resolved_contents = self.resolve_contents(env, force=True)
        if not resolved_contents:
            raise BuildError('empty bundle cannot be built')

        # Prepare filters
        filters = merge_filters(self.filters, extra_filters)
        for filter in filters:
            filter.set_environment(env)
            # Since we call this now every single time before the filter
            # is used, we might pass the bundle instance it is going
            # to be used with. For backwards-compatibility reasons, this
            # is problematic. However, by inspecting the support arguments,
            # we can deal with it. We probably then want to deprecate
            # the old syntax before 1.0 (TODO).
            filter.setup()

        # Unless we have been told by our caller to use or not use the
        # cache for this, try to decide for ourselves. The issue here
        # is that when a bundle has dependencies, like a sass file with
        # includes otherwise not listed in the bundle sources, a change
        # in such an external include would not influence the cache key,
        # those the use of the cache causing such a change to be ignored.
        # For now, we simply do not use the cache for any bundle with
        # dependencies.  Another option would be to read the contents of
        # all files declared via "depends", and use them as a cache key
        # modifier. For now I am worried about the performance impact.
        #
        # Note: This decision only affects the current bundle instance.
        # Even if dependencies cause us to ignore the cache for this
        # bundle instance, child bundles may still use it!
        if disable_cache is None:
            actually_skip_cache_here = bool(self.resolve_depends(env))
        else:
            actually_skip_cache_here = disable_cache

        filtertool = FilterTool(
            env.cache, no_cache_read=actually_skip_cache_here,
            kwargs={'output': output,
                    'output_path': env.abspath(output)})

        # Apply input filters to all the contents. Note that we use both this
        # bundle's filters as well as those given to us by the parent. We ONLY
        # do those this for the input filters, because we need them to be
        # applied before the apply our own output filters.
        combined_filters = merge_filters(filters, parent_filters)
        hunks = []
        for rel_name, item in resolved_contents:
            if isinstance(item, Bundle):
                hunk = item._merge_and_apply(
                    env, output, force, debug,
                    combined_filters, disable_cache=disable_cache)
                hunks.append(hunk)
            else:
                # Pass along the original relative path, as specified by the
                # user. This may differ from the actual filesystem path, if
                # extensions provide a virtualized filesystem (e.g. Flask
                # blueprints, Django staticfiles).
                kwargs = {'source': rel_name}

                # Give a filter the chance to open his file.
                try:
                    hunk = filtertool.apply_func(
                        combined_filters, 'open', [item], kwargs=kwargs)
                except MoreThanOneFilterError, e:
                    raise BuildError(e)

                if not hunk:
                    if is_url(item):
                        hunk = UrlHunk(item)
                    else:
                        hunk = FileHunk(item)

                if no_filters:
                    hunks.append(hunk)
                else:
                    hunks.append(filtertool.apply(
                        hunk, combined_filters, 'input', kwargs=kwargs))

        # Merge the individual files together.
        try:
            final = filtertool.apply_func(combined_filters, 'concat', [hunks])
            if final is None:
                final = merge(hunks)
        except (IOError, MoreThanOneFilterError), e:
            raise BuildError(e)

        # Apply output filters, if there are any.
        if no_filters:
            return final
        else:
            # TODO: So far, all the situations where bundle dependencies
            # are used/useful, are based on input filters having those
            # dependencies. Is it even required to consider them here
            # with respect to the cache? We might be able to run this
            # operation with the cache on (the FilterTool being possibly
            # configured with cache reads off).
            return filtertool.apply(final, filters, 'output')

    def _build(self, env, extra_filters=[], force=None, output=None,
               disable_cache=None):
        """Internal bundle build function.

        This actually tries to build this very bundle instance, as opposed to
        the public-facing ``build()``, which first deals with the possibility
        that we are a container bundle, i.e. having no files of our own.

        First checks whether an update for this bundle is required, via the
        configured ``updater`` (which is almost always the timestamp-based one).
        Unless ``force`` is given, in which case the bundle will always be
        built, without considering timestamps.

        Note: The default value of ``force`` is normally ``False``, unless
        ``auto_build`` is disabled, in which case ``True`` is assumed.

        A ``FileHunk`` will be returned, or in a certain case, with no updater
        defined and force=False, the return value may be ``False``.

        TODO: Support locking. When called from inside a template tag, this
        should lock, so that multiple requests don't all start to build. When
        called from the command line, there is no need to lock.
        """

        if not self.output:
            raise BuildError('No output target found for %s' % self)

        # Default force to True if auto_build is disabled, as otherwise
        # no build would happen. This is only a question of API design.
        # We want auto_build=False users to be able to call bundle.build()
        # and have it have an effect.
        if force is None:
            force = not env.auto_build

        # Determine if we really need to build, or if the output file
        # already exists and nothing has changed.
        if force:
            update_needed = True
        elif not env.auto_build:
            # If the user disables the updater, he expects to be able
            # to manage builds all on his one. Don't even bother wasting
            # IO ops on an update check. It's also convenient for
            # deployment scenarios where the media files are on a different
            # server, and we can't even access the output file.
            return False
        elif not has_placeholder(self.output) and \
                not path.exists(env.abspath(self.output)):
            update_needed = True
        else:
            if env.auto_build:
                update_needed = env.updater.needs_rebuild(self, env)
                # _merge_and_apply() is now smart enough to do without
                # this disable_cache hint, but for now, keep passing it
                # along if we get the info from the updater.
                if update_needed==SKIP_CACHE:
                    disable_cache = True
            else:
                update_needed = False

        if not update_needed:
            # We can simply return the existing output file
            return FileHunk(env.abspath(self.output))

        hunk = self._merge_and_apply(
            env, self.output, force,
            disable_cache=disable_cache,
            extra_filters=extra_filters)

        if output:
            # If we are given a stream, just write to it.
            output.write(hunk.data())
        else:
            # If it doesn't exist yet, create the target directory.
            output = env.abspath(self.output)
            output_dir = path.dirname(output)
            if not path.exists(output_dir):
                os.makedirs(output_dir)

            version = None
            if env.versions:
                version = env.versions.determine_version(self, env, hunk)

            if not has_placeholder(self.output):
                hunk.save(self.resolve_output(env))
            else:
                if not env.versions:
                    raise BuildError((
                        'You have not set the "versions" option, but %s '
                        'uses a version placeholder in the output target'
                            % self))
                output = self.resolve_output(env, version=version)
                hunk.save(output)
                self.version = version

            if env.manifest:
                env.manifest.remember(self, env, version)
            if env.versions and version:
                # Hook for the versioner (for example set the timestamp of
                # the file) to the actual version.
                env.versions.set_version(self, env, output, version)

        # The updater may need to know this bundle exists and how it
        # has been last built, in order to detect changes in the
        # bundle definition, like new source files.
        env.updater.build_done(self, env)

        return hunk

    def build(self, env=None, force=None, output=None, disable_cache=None):
        """Build this bundle, meaning create the file given by the
        ``output`` attribute, applying the configured filters etc.

        If the bundle is a container bundle, then multiple files will
        be built.

        Unless ``force`` is given, the configured ``updater`` will be
        used to check whether a build is even necessary. However,
        if ``auto_build`` has been disabled, then ``True`` is assumed
        for ``force``.

        If ``output`` is a file object, the result will be written to it
        rather than to the filesystem.

        The return value is a list of ``FileHunk`` objects, one for
        each bundle that was built.
        """
        env = self._get_env(env)
        hunks = []
        for bundle, extra_filters in self.iterbuild(env):
            hunks.append(bundle._build(
                env, extra_filters, force=force, output=output,
                disable_cache=disable_cache))
        return hunks

    def iterbuild(self, env=None):
        """Iterate over the bundles which actually need to be built.

        This will often only entail ``self``, though for container
        bundles (and container bundle hierarchies), a list of all the
        non-container leafs will be yielded.

        Essentially, what this does is "skip" bundles which do not need
        to be built on their own (container bundles), and gives the
        caller the child bundles instead.

        The return values are 2-tuples of (bundle, filter_list), with
        the second item being a list of filters that the parent
        "container bundles" this method is processing are passing down
        to the children.
        """
        env = self._get_env(env)
        if self.is_container:
            for bundle, _ in self.resolve_contents(env):
                if bundle.is_container:
                    for child, child_filters in bundle.iterbuild(env):
                        yield child, merge_filters(child_filters, self.filters)
                else:
                    yield bundle, self.filters
        else:
            yield self, []

    def _make_url(self, env):
        """Return a output url, modified for expire header handling.
        """

        # Only query the version if we need to for performance
        version = None
        if has_placeholder(self.output) or env.url_expire != False:
            # If auto-build is enabled, we must not use a cached version
            # value, or we might serve old versions.
            version = self.get_version(env, refresh=env.auto_build)

        result = self.resolve_output(env, version, rel=True)
        if env.url_expire or (
                env.url_expire is None and not has_placeholder(self.output)):
            result = "%s?%s" % (result, version)
        return env.absurl(result)

    def _urls(self, env, extra_filters, *args, **kwargs):
        # Resolve debug: see whether we have to merge the contents
        debug = self.debug if self.debug is not None else env.debug
        if debug == 'merge':
            supposed_to_merge = True
        elif debug is True:
            supposed_to_merge = False
        elif debug is False:
            supposed_to_merge = True
        else:
            raise BundleError('Invalid debug value: %s' % debug)

        if supposed_to_merge and (self.filters or self.output):
            # We need to build this bundle, unless a) the configuration
            # tells us not to ("supposed_to_merge"), or b) this bundle
            # isn't actually configured to be built, that is, has no
            # filters and no output target.
            hunk = self._build(env, extra_filters=extra_filters,
                               force=False, *args, **kwargs)
            return [self._make_url(env)]
        else:
            # We either have no files (nothing to build), or we are
            # in debug mode: Instead of building the bundle, we
            # source all contents instead.
            urls = []
            for c, _ in self.resolve_contents(env):
                if isinstance(c, Bundle):
                    urls.extend(c.urls(env, *args, **kwargs))
                elif is_url(c):
                    urls.append(c)
                else:
                    urls.append(env.absurl(c))
            return urls

    def urls(self, env=None, *args, **kwargs):
        """Return a list of urls for this bundle.

        Depending on the environment and given options, this may be a
        single url (likely the case in production mode), or many urls
        (when we source the original media files in DEBUG mode).

        Insofar necessary, this will automatically create or update
        the files behind these urls.
        """
        env = self._get_env(env)
        urls = []
        for bundle, extra_filters in self.iterbuild(env):
            urls.extend(bundle._urls(env, extra_filters, *args, **kwargs))
        return urls


def get_all_bundle_files(bundle, env=None):
    """Return a flattened list of all source files of the given
    bundle, all it's dependencies, recursively for all nested
    bundles.

    Making this a helper function rather than a part of the official
    Bundle feels right.
    """
    env = bundle._get_env(env)
    files = []
    for _, c in bundle.resolve_contents(env):
        if isinstance(c, Bundle):
            files.extend(get_all_bundle_files(c, env))
        elif not is_url(c):
            files.append(c)
        files.extend(bundle.resolve_depends(env))
    return files
