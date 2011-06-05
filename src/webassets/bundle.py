from os import path
import urlparse
import glob
import warnings
from filter import get_filter
from merge import (FileHunk, MemoryHunk, UrlHunk, apply_filters, merge,
                   make_url, merge_filters)
from updater import SKIP_CACHE


__all__ = ('Bundle', 'BundleError', 'get_all_bundle_files',)


class BundleError(Exception):
    pass


class BuildError(BundleError):
    pass


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

    def resolve_contents(self, env=None):
        """Returns contents, with globbed patterns resolved to
        actual filenames.
        """
        env = self._get_env(env)

        # TODO: We cache the values, which in theory is problematic, since
        # due to changes in the env object, the result of the globbing may
        # change. Not to mention that a different env object may be passed
        # in. We should find a fix for this.
        if getattr(self, '_resolved_contents', None) is None:
            l = []
            for item in self.contents:
                if isinstance(item, basestring):
                    # We only go through glob() if this actually is a
                    # pattern; this means that invalid filenames will
                    # remain in the content set, and only raise an error
                    # at a later point in time.
                    # TODO: This is possible a good place to check for
                    # a file's existence though; currently, when in debug
                    # mode, no error would be raised at all, and simply a
                    # broken url sent to the browser.
                    if glob.has_magic(item):
                        path = env.abspath(item)
                        for f in glob.glob(path):
                            l.append(f[len(path)-len(item):])
                    else:
                        l.append(item)
                else:
                    l.append(item)
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
        # Caching is as problematic here as it is in resolve_contents().
        if not self.depends:
            return []
        if getattr(self, '_resolved_depends', None) is None:
            l = []
            for item in self.depends:
                if isinstance(item, basestring):
                    if glob.has_magic(item):
                        path = env.abspath(item)
                        for f in glob.glob(path):
                            l.append(f[len(path)-len(item):])
                    else:
                        l.append(item)
                else:
                    l.append(item)
            self._resolved_depends = l
        return self._resolved_depends

    def get_files(self, env=None):
        warnings.warn('Bundle.get_files() has been replaced '+
                      'by get_all_bundle_files() utility. '+
                      'This API be removed in 0.6.')
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

    def _build(self, env, output_path, force, no_filters=False,
               parent_filters=[], disable_cache=False):
        """Internal recursive build method.
        """

        # Look at the bundle's ``debug`` option to decide what
        # building it entails.
        debug = self.debug if self.debug is not None else env.debug
        if debug is None:
            # work with whatever no_filters was passed by the parent
            pass
        elif debug == 'merge':
            no_filters = True
        elif debug is True:
            # This should be caught by urls().
            raise BuildError("a bundle with debug=True cannot be built")
        elif debug is False:
            no_filters = False
        else:
            raise BundleError('Invalid debug value: %s' % debug)

        resolved_contents = self.resolve_contents(env)
        if not resolved_contents:
            raise BuildError('empty bundle cannot be built')

        # Ensure that the filters are ready
        for filter in self.filters:
            filter.set_environment(env)

        # Apply input filters to all the contents. Note that we use
        # both this bundle's filters as well as those given to us by
        # the parent. We ONLY do those this for the input filters,
        # because we need them to be applied before the apply our own
        # output filters.
        # TODO: Note that merge_filters() removes duplicates. Is this
        # really the right thing to do, or does it just confuse things
        # due to there now being different kinds of behavior...
        combined_filters = merge_filters(self.filters, parent_filters)
        hunks = []
        for c in resolved_contents:
            if isinstance(c, Bundle):
                hunk = c._build(env, output_path, force, no_filters,
                                combined_filters, disable_cache)
                hunks.append(hunk)
            else:
                if is_url(c):
                    hunk = UrlHunk(c)
                else:
                    hunk = FileHunk(env.abspath(c))
                if no_filters:
                    hunks.append(hunk)
                else:
                    hunks.append(apply_filters(
                        hunk, combined_filters, 'input',
                        env.cache, disable_cache,
                        output_path=output_path))

        # Return all source hunks as one, with output filters applied
        final = merge(hunks)
        if no_filters:
            return final
        else:
            return apply_filters(final, self.filters, 'output',
                                 env.cache, disable_cache)

    def build(self, env=None, force=False):
        """Build this bundle, meaning create the file given by the
        ``output`` attribute, applying the configured filters etc.

        A ``FileHunk`` will be returned.

        TODO: Support locking. When called from inside a template tag,
        this should lock, so that multiple requests don't all start
        to build. When called from the command line, there is no need
        to lock.
        """

        if not self.output:
            raise BuildError('No output target found for %s' % self)

        env = self._get_env(env)

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
            update_needed = env.updater.needs_rebuild(self, env)

        if not update_needed:
            # We can simply return the existing output file
            return FileHunk(env.abspath(self.output))

        hunk = self._build(env, self.output, force,
                           disable_cache=update_needed==SKIP_CACHE)
        hunk.save(env.abspath(self.output))

        # The updater may need to know this bundle exists and how it
        # has been last built, in order to detect changes in the
        # bundle definition, like new source files.
        if env.updater:
            env.updater.build_done(self, env)

        return hunk

    def iterbuild(self, env=None):
        """Iterate over the bundles which actually need to be built.

        This will often only entail ``self``, though for container
        bundles (and container bundle hierarchies), a list of all the
        non-container leafs will be yielded.

        Essentially, what this does is "skip" bundles which do not need
        to be built on their own (container bundles), and gives the
        caller the child bundles instead.
        """
        env = self._get_env(env)
        if self.is_container:
            for bundle in self.resolve_contents(env):
                if bundle.is_container:
                    for t in bundle.iterbuild(env):
                        yield t
                else:
                    yield bundle
        else:
            yield self

    def _urls(self, env, *args, **kwargs):
        env = self._get_env(env)

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
            # tells us not to ("determine_action"), or b) this bundle
            # isn't actually configured to be built, that is, has no
            # filters and no output target.
            hunk = self.build(env, *args, **kwargs)
            return [make_url(env, self.output)]
        else:
            # We either have no files (nothing to build), or we are
            # in debug mode: Instead of building the bundle, we
            # source all contents instead.
            urls = []
            for c in self.resolve_contents(env):
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
        urls = []
        for bundle in self.iterbuild(env):
            urls.extend(bundle._urls(env, *args, **kwargs))
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
    for c in bundle.resolve_contents(env):
        if isinstance(c, Bundle):
            files.extend(get_all_bundle_files(c, env))
        elif not is_url(c):
            files.append(env.abspath(c))
        files.extend(bundle.resolve_depends(env))
    return files
