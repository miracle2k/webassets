from os import path
import glob
from updater import get_updater
from filter import get_filter
from cache import get_cache
from merge import (FileHunk, MemoryHunk, apply_filters, merge,
                   make_url, merge_filters)


__all__ = ('Bundle', 'BundleError',)


class BundleError(Exception):
    pass


class BuildError(BundleError):
    pass


class Bundle(object):
    """A bundle is the unit django-assets uses to organize groups of media
    files, which filters to apply and where to store them.

    Bundles can be nested.
    """

    def __init__(self, *contents, **options):
        self.env = None
        self.contents = contents
        self.output = options.get('output')
        self.filters = options.get('filters')
        self.debug = options.get('debug')
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

    def resolve_contents(self, env):
        """Returns contents, with globbed patterns resolved to actual
        filenames.
        """
        # TODO: We cache the values, which in theory is problematic, since
        # due to changes in the env object, the result of the globbing may
        # change. Not to mention that a different env object may be passed
        # in. We should find a fix for this.
        if not getattr(self, '_resolved_contents', None):
            l = []
            for item in self.contents:
                if isinstance(item, basestring):
                    # We only go through glob() if this actually is a
                    # pattern; this means that invalid filenames will
                    # remain in the content set, and only raise an error
                    # at a later point in time.
                    # TODO: This is possible a good place to check for
                    # a file's existance though; currently, when in debug
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
        """Return a flattened list of all source files of this bundle,
        and all the nested bundles.
        """
        env = self._get_env(env)
        files = []
        for c in self.resolve_contents(env):
            if isinstance(c, Bundle):
                files.extend(c.get_files(env))
            else:
                files.append(env.abspath(c))
        return files

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

    def _build(self, env, output_path, force, no_filters, parent_filters=[]):
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
        cache = get_cache(env)
        hunks = []
        for c in resolved_contents:
            if isinstance(c, Bundle):
                hunk = c._build(env, output_path, force, no_filters,
                                combined_filters)
                hunks.append(hunk)
            else:
                hunk = FileHunk(env.abspath(c))
                if no_filters:
                    hunks.append(hunk)
                else:
                    hunks.append(apply_filters(
                        hunk, combined_filters, 'input', cache,
                        output_path=output_path))

        # Return all source hunks as one, with output filters applied
        final = merge(hunks)
        if no_filters:
            return final
        else:
            return apply_filters(final, self.filters, 'output', cache)

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
            source_paths = [p for p in self.get_files(env)]
            update_needed = get_updater(env.updater)(
                env.abspath(self.output), source_paths)

        if not update_needed:
            # We can simply return the existing output file
            return FileHunk(env.abspath(self.output))

        hunk = self._build(env, self.output, force, no_filters)
        hunk.save(env.abspath(self.output))
        return hunk

    def iterbuild(self, env=None):
        """Iterate over the bundles which actually need to be built.

        This will often only entail ``self``, though for container
        bundles (and container bundle hierarchies), a list of all the
        non-container leafs will be yielded.

        Essentally, what this does is "skip" bundles which do not need
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
