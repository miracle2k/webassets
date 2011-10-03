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
                   make_url, merge_filters)
from updater import SKIP_CACHE
from exceptions import BundleError, BuildError


__all__ = ('Bundle', 'get_all_bundle_files',)


def is_url(s):
    return bool(urlparse.urlsplit(s).scheme)


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
        return "<Bundle output=%s, filters=%s, contents=%s>" % (
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
                if isinstance(item, basestring):
                    if is_url(item):
                        # Is a URL
                        l.append((item, item))
                    elif has_magic(item):
                        # Is globbed pattern
                        path = env.abspath(item)
                        for f in glob.glob(path):
                            l.append((f[len(path)-len(item):], f))
                    else:
                        # Is just a normal path; Send it through
                        # _normalize_source_path().
                        try:
                            l.append((item, env._normalize_source_path(item)))
                        except IOError, e:
                            raise BundleError(e)
                else:
                    # Is probably a nested Bundle
                    l.append((item, item))
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
                         disable_cache=False):
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
        cache.
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
                        env.cache, disable_cache,
                        output_path=output_path))

        # Return all source hunks as one, with output filters applied
        try:
            final = merge(hunks)
        except IOError, e:
            raise BuildError(e)

        if no_filters:
            return final
        else:
            return apply_filters(final, filters, 'output',
                                 env.cache, disable_cache)

    def _build(self, env, extra_filters=[], force=False):
        """Internal bundle build function.

        Check if an update for this bundle is required, and if so,
        build it.

        A ``FileHunk`` will be returned.

        TODO: Support locking. When called from inside a template tag,
        this should lock, so that multiple requests don't all start
        to build. When called from the command line, there is no need
        to lock.
        """

        if not self.output:
            raise BuildError('No output target found for %s' % self)

        # Determine if we really need to build, or if the output file
        # already exists and nothing has changed.
        if force:
            update_needed = True
        elif not path.exists(env.abspath(self.output)):
            if not env.updater:
                raise BuildError(('\'%s\' needs to be created, but '
                                  'automatic building is disabled  ('
                                  'configure an updater)') % self)
            else:
                update_needed = True
        else:
            if env.updater:
                update_needed = env.updater.needs_rebuild(self, env)
            else:
                update_needed = False

        if not update_needed:
            # We can simply return the existing output file
            return FileHunk(env.abspath(self.output))

        hunk = self._merge_and_apply(
            env, self.output, force,
            disable_cache=update_needed==SKIP_CACHE,
            extra_filters=extra_filters)
        hunk.save(env.abspath(self.output))

        # The updater may need to know this bundle exists and how it
        # has been last built, in order to detect changes in the
        # bundle definition, like new source files.
        if env.updater:
            env.updater.build_done(self, env)

        return hunk

    def build(self, env=None, force=False):
        """Build this bundle, meaning create the file given by the
        ``output`` attribute, applying the configured filters etc.

        If the bundle is a container bundle, then multiple files will
        be built.

        The return value is a list of ``FileHunk`` objects, one for
        each bundle that was built.
        """
        env = self._get_env(env)
        hunks = []
        for bundle, extra_filters in self.iterbuild(env):
            hunks.append(bundle._build(env, extra_filters, force=force))
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
                               *args, **kwargs)
            return [make_url(env, self.output)]
        else:
            # We either have no files (nothing to build), or we are
            # in debug mode: Instead of building the bundle, we
            # source all contents instead.
            urls = []
            for c, _ in self.resolve_contents(env):
                if isinstance(c, Bundle):
                    urls.extend(c.urls(env, *args, **kwargs))
                else:
                    urls.append(make_url(env, c, expire=False))
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
