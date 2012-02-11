import os
from os import path
import urlparse
try:
    # Current version of glob2 does not let us access has_magic :/
    import glob2 as glob
    from glob import has_magic
except ImportError:
    import glob
    from glob import has_magic
import warnings
from filter import get_filter
from merge import (FileHunk, MemoryHunk, UrlHunk, apply_filters, merge,
                   merge_filters)
from updater import SKIP_CACHE
from exceptions import BundleError, BuildError


__all__ = ('Bundle', 'get_all_bundle_files',)


def is_url(s):
    if not isinstance(s, str):
        return False
    scheme = urlparse.urlsplit(s).scheme
    return bool(scheme) and len(scheme) > 1

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
        """Convert bundle contents into something that can be easily
        processed.

        - Glob patterns are resolved
        - Validate all the source paths to complain about
          missing files early.
        - Third party extensions get to hook into this to
          provide a basic virtualized filesystem.

        The return value is a list of 2-tuples (relpath, abspath).
        The first element is the path that is assumed to be relative
        to the ``Environment.directory`` value. We need it to construct
        urls to the source files.
        The second element is the absolute path to the actual location
        of the file. Depending on the magic a third party extension
        does, this may be somewhere completely different.

        URLs and nested Bundles are returned as a 2-tuple where
        both items are the same.

        Set ``force`` to ignore any cache, and always re-resolve
        glob patterns.
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

    def get_files(self, env=None):
        warnings.warn('Bundle.get_files() has been replaced '+
                      'by get_all_bundle_files() utility. '+
                      'This API be removed in 0.7.')
        return get_all_bundle_files(self, env)

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

    def _merge_and_apply(self, env, output_path, force, parent_debug=None,
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

        # Apply input filters to all the contents. Note that we use
        # both this bundle's filters as well as those given to us by
        # the parent. We ONLY do those this for the input filters,
        # because we need them to be applied before the apply our own
        # output filters.
        combined_filters = merge_filters(filters, parent_filters)
        hunks = []
        for _, c in resolved_contents:
            if isinstance(c, Bundle):
                hunk = c._merge_and_apply(
                    env, output_path, force, debug,
                    combined_filters, disable_cache=disable_cache)
                hunks.append(hunk)
            else:
                if is_url(c):
                    hunk = UrlHunk(c)
                else:
                    hunk = FileHunk(c)
                if no_filters:
                    hunks.append(hunk)
                else:
                    hunks.append(apply_filters(
                        hunk, combined_filters, 'input',
                        env.cache, actually_skip_cache_here,
                        output_path=output_path))

        # Return all source hunks as one, with output filters applied
        try:
            final = merge(hunks)
        except IOError, e:
            raise BuildError(e)

        if no_filters:
            return final
        else:
            # TODO: So far, all the situations where bundle dependencies
            # are used/useful, are based on input filters having those
            # dependencies. Is it even required to consider them here
            # with respect to the cache?
            return apply_filters(final, filters, 'output',
                                 env.cache, actually_skip_cache_here)

    def _build(self, env, extra_filters=[], force=None, output=None,
               disable_cache=None):
        """Internal bundle build function.

        This actually tries to build this very bundle instance, as
        opposed to the public-facing ``build()``, which first deals
        with the possibility that we are a container bundle, i.e.
        having no files of our own.

        First checks whether an update for this bundle is required,
        via the configured ``updater`` (which is almost always the
        timestamp-based one). Unless ``force`` is given, in which
        case the bundle will always be built, without considering
        timestamps.

        Note: The default value of ``force`` is normally ``False``,
        unless no ``updater`` is configured, in which case ``True``
        is assumed.

        A ``FileHunk`` will be returned, or in a certain case, with
        no updater defined and force=False, the return value may be
        ``False``.

        TODO: Support locking. When called from inside a template tag,
        this should lock, so that multiple requests don't all start
        to build. When called from the command line, there is no need
        to lock.
        """

        if not self.output:
            raise BuildError('No output target found for %s' % self)

        # Default force to True if no updater is given, as otherwise
        # no build would happen. This is only a question of API design.
        # We want updater=False users to be able to call bundle.build()
        # and have it have an effect.
        if force is None:
            force = not bool(env.updater)

        # Determine if we really need to build, or if the output file
        # already exists and nothing has changed.
        if force:
            update_needed = True
        elif not env.updater:
            # If the user disables the updater, he expects to be able
            # to manage builds all on his one. Don't even bother wasting
            # IO ops on an update check. It's also convenient for
            # deployment scenarios where the media files are on a different
            # server, and we can't even access the output file.
            return False
        elif not path.exists(env.abspath(self.output)):
            update_needed = True
        else:
            if env.updater:
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
        if not output:
            # If it doesn't exist yet, create the target directory.
            filename = env.abspath(self.output)
            output_dir = path.dirname(filename)
            if not path.exists(output_dir):
                os.makedirs(output_dir)
            hunk.save(filename)
        else:
            output.write(hunk.data())

        # The updater may need to know this bundle exists and how it
        # has been last built, in order to detect changes in the
        # bundle definition, like new source files.
        if env.updater:
            env.updater.build_done(self, env)

        return hunk

    def build(self, env=None, force=None, output=None, disable_cache=None):
        """Build this bundle, meaning create the file given by the
        ``output`` attribute, applying the configured filters etc.

        If the bundle is a container bundle, then multiple files will
        be built.

        Unless ``force`` is given, the configured ``updater`` will be
        used to check whether a build is even necessary. However,
        if the updater has been explicitly disabled, then ``True``
        is assumed for ``force``.

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

    def _make_url(self, env, filename, expire=True):
        """Return a output url, modified for expire header handling.

        Set ``expire`` to ``False`` if you do not want the URL to
        be modified for cache busting.
        """
        if expire:
            path = env.abspath(filename)
            if env.expire == 'querystring':
                last_modified = os.stat(path).st_mtime
                result = "%s?%d" % (filename, last_modified)
            elif env.expire == 'filename':
                last_modified = os.stat(path).st_mtime
                name = filename.rsplit('.', 1)
                if len(name) > 1:
                    result = "%s.%d.%s" % (name[0], last_modified, name[1])
                else:
                    result = "%s.%d" % (name, last_modified)
            elif not env.expire:
                result = filename
            else:
                raise ValueError('Unknown value for ASSETS_EXPIRE option: %s' %
                                     env.expire)
        else:
            result = filename
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
            return [self._make_url(env, self.output)]
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
                    urls.append(self._make_url(env, c, expire=False))
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
