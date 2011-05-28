from os import path
import urlparse
import glob
import os
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

    def get_version(self, env):
        """Return the current version of the Bundle.

        If this is not yet set via ``Bundle.version``, then the
        versioner will be used to determine it.

        If the output filename contains a %(version)s placeholder,
        when we're facing a hard problem to solve: The problem, in
        general terms, removed from this particular function, is: the
        asset may already have been created out-of-process, but how do
        we know what filename/url we have to render? There are only a
        limited number of answers:

        1. Make the version discernible from the source files. In the
           case of a TimestampVersion, the built output file needs to be
           explicitly set to the maximum timestamp of the sources. Or, in
           the case of HashVersion, the hash needs to be built over the
           source files + asset definitions rather than the output file.
           This is rife with trouble though: Imagine for example a filter
           has a bug, creates erroneous output. Fixing the filter would
           change the output, but not the version hash. Plus Bundle.depends
           would need to be included, and I'm not comfortable making it
           this important.

        2. The version is persisted in the cache. Would only work for an
           out-of-process cache though.

        3. We always create two output files, one with the actual version,
           and one with a fixed version string. The latter will be used to
           restore the current version in a new process.

        4. A variation to using the environment cache would be to have a
           separate ".webassets-version" file just for this stuff.

        Currently, a combination of (2) and (3) is used. If a persistent
        cache is available, it will be used; otherwise, a build will
        create an output file with a static version string.
        """
        env = self._get_env(env)
        if not self.version:
            if has_variable(self.output):
                if env.cache:
                    # only do this if the cache is persistent
                    # should be create a .webassets-versions directory instead?
                    self.version = env.cache.get(('version', self.get_output()))
                else:
                    # try get_version_for() with fixed %(version)s string
                    pass
            else:
                self.version = env.versioner.get_version_for(self)
        return self.version

    def get_output(self, env, version=None):
        """Return the full, absolute output path.

        If a %(version)s placeholder is used, it is replaced.
        """
        env = self._get_env(env)
        output = self.output
        if has_placeholder(output):
            output = output % {'version': version or self.get_version()}
        return env.abspath(output)


    def determine_action(self, env):
        """Decide what needs to be done when this bundle needs to be
        resolved.

        Specifically, whether to apply filters and whether to merge. This
        depends on both the global settings, as well as the ``debug``
        attribute of this bundle.

        Returns a 2-tuple of (should_merge, should_filter). The latter
        always implies the former.
        """
        if not env.debug:
            return True, True

        debug = self.debug if self.debug is not None else env.debug

        if debug == 'merge':
            return True, False
        elif debug is True:
            return False, False
        elif debug is False:
            return True, True
        else:
            raise BundleError('Invalid debug value: %s' % debug)

    def get_files(self, env=None):
        warnings.warn('Bundle.get_files() has been replaced '+
                      'by get_all_bundle_files() utility. '+
                      'This API is to be removed in 0.6.')
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

    def _build(self, env, output_path, force, no_filters, parent_filters=[],
               disable_cache=False):
        """Internal recursive build method.
        """

        # TODO: We could support a nested bundle downgrading it's debug
        # setting from "filters" to "merge only", i.e. enabling
        # ``no_filters``. We cannot support downgrading to
        # "full debug/no merge" (debug=True), of course.
        #
        # Right now we simply use the debug setting of the root bundle
        # we build, und it overrides all the nested bundles. If we
        # allow nested bundles to overwrite the debug value of parent
        # bundles, as described above, then we should also deal with
        # a child bundle enabling debug=True during a merge, i.e.
        # raising an error rather than ignoring it as we do now.
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

    def build(self, env=None, force=False, no_filters=False):
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
        update_needed = False
        if force:
            update_needed = True
        elif not path.exists(env.abspath(self.output)):
            if not env.auto_build:
                raise BuildError(('\'%s\' needs to be created, but '
                                  'automatic building is disabled (set '
                                  'the "auto_build" option') % self)
            else:
                update_needed = True
        elif env.auto_build:
            update_needed = env.versioner.updater.needs_rebuild(self, env)

        if not update_needed:
            # We can simply return the existing output file
            return FileHunk(env.abspath(self.output))

        hunk = self._build(env, self.output, force, no_filters,
                           disable_cache=update_needed==SKIP_CACHE)

        if not has_placeholder(self.output):
            hunk.save(self.get_output(env))
        else:
            temp = make_temp_output(self)
            hunk.save(temp)
            # refresh the version
            self.version = env.versioner.get_version_for(temp)
            os.rename(temp, self.get_output())
            if not (env.cache and env.cache.is_persistent):
                static = self.get_output(version='static')
                hunk.save(static)
                # Give timestamp versioner a change to set the timestamp
                # to the same value as the actual versioned file.
                env.versioner.set_version(static, self.version)

        # The updater may need to know this bundle exists and how it
        # has been last built, in order to detect changes in the
        # bundle definition, like new source files.
        if env.versioner and env.versioner.updater:
            env.versioner.updater.build_done(self, env)

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
        supposed_to_merge, do_filter = self.determine_action(env)

        if supposed_to_merge and (self.filters or self.output):
            # We need to build this bundle, unless a) the configuration
            # tells us not to ("determine_action"), or b) this bundle
            # isn't actually configured to be built, that is, has no
            # filters and no output target.
            hunk = self.build(env, no_filters=not do_filter, *args, **kwargs)
            return [make_url(env, self)]
        else:
            # We either have no files (nothing to build), or we are
            # in debug mode: Instead of building the bundle, we
            # source all contents instead.
            urls = []
            for c in self.resolve_contents(env):
                if isinstance(c, Bundle):
                    urls.extend(c.urls(env, *args, **kwargs))
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
