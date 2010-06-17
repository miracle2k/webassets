from os import path
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
        self.manager = None
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
            filters = value.split(',')
        elif isinstance(value, (list, tuple)):
            filters = value
        else:
            filters = [value]
        self._filters = [get_filter(f) for f in filters]
    filters = property(_get_filters, _set_filters)

    def determine_action(self, manager):
        """Decide what needs to be done when this bundle needs to be
        resolved.

        Specifically, whether to apply filters and whether to merge. This
        depends on both the global settings, as well as the ``debug``
        attribute of this bundle.

        Returns a 2-tuple of (should_merge, should_filter). The latter
        always implies the former.
        """
        if not manager.debug:
            return True, True

        debug = self.debug if self.debug is not None else manager.debug

        if debug == 'merge':
            return True, False
        elif debug is True:
            return False, False
        elif debug is False:
            return True, True
        else:
            raise BundleError('Invalid debug value: %s' % debug)

    def get_files(self):
        """Return a flattened list of all source files of this bundle,
        and all the nested bundles.
        """
        files = []
        for c in self.contents:
            if isinstance(c, Bundle):
                files.extend(c.get_files())
            else:
                files.append(c)
        return files

    def _get_manager(self, manager):
        # Note how bool(manager) can be False, due to __len__.
        manager = manager if manager is not None else self.manager
        if manager is None:
            raise BundleError('Bundle is not connected to a manager')
        return manager

    def _build(self, manager, output_path, force, no_filters, parent_filters=[]):
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

        if not self.contents:
            raise BuildError('empty bundle cannot be built')

        # Ensure that the filters are ready
        for filter in self.filters:
            filter.set_manager(manager)

        # Apply input filters to all the contents. Note that we use
        # both this bundle's filters as well as those given to us by
        # the parent. We ONLY do those this for the input filters,
        # because we need them to be applied before the apply our own
        # output filters.
        # TODO: Note that merge_filters() removes duplicates. Is this
        # really the right thing to do, or does it just confuse things
        # due to there now being different kinds of behavior...
        combined_filters = merge_filters(self.filters, parent_filters)
        cache = get_cache(manager)
        hunks = []
        for c in self.contents:
            if isinstance(c, Bundle):
                hunk = c._build(manager, output_path, force, no_filters,
                                combined_filters)
                hunks.append(hunk)
            else:
                hunk = FileHunk(manager.abspath(c))
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

    def build(self, manager=None, force=False, no_filters=False):
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

        manager = self._get_manager(manager)

        # Determine if we really need to build, or if the output file
        # already exists and nothing has changed.
        if force:
            update_needed = True
        elif not path.exists(manager.abspath(self.output)):
            if not self.manager.auto_create:
                raise BuildError(('\'%s\' needs to be created, but '
                                  'ASSETS_AUTO_CREATE is disabled') % self)
            else:
                update_needed = True
        else:
            source_paths = [manager.abspath(p) for p in self.get_files()]
            update_needed = get_updater(manager.updater)(
                manager.abspath(self.output), source_paths)

        if not update_needed:
            # We can simply return the existing output file
            return FileHunk(manager.abspath(self.output))

        hunk = self._build(manager, self.output, force, no_filters)
        hunk.save(manager.abspath(self.output))
        return hunk

    def urls(self, manager=None, *args, **kwargs):
        """Return a list of urls for this bundle.

        Depending on the environment and given options, this may be a
        single url (likely the case in production mode), or many urls
        (when we source the original media files in DEBUG mode).

        Insofar necessary, this will automatically create or update
        the files behind these urls.
        """

        manager = self._get_manager(manager)

        has_files = any([c for c in self.contents if not isinstance(c, Bundle)])
        supposed_to_merge, do_filter = self.determine_action(manager)

        if (self.output or has_files) and supposed_to_merge:
            # If this bundle has an output target, then we want to build
            # it, if it has files, then we need to build it, at least
            # as long as were not explicitely allowed to not build at all,
            # e.g. in debug mode.
            hunk = self.build(manager, no_filters=not do_filter, *args, **kwargs)
            return [make_url(manager, self.output)]
        else:
            # We either have no files (nothing to build), or we are
            # in debug mode: Instead of building the bundle, we
            # source all contents instead.
            urls = []
            for c in self.contents:
                if isinstance(c, Bundle):
                    urls.extend(c.urls(manager, *args, **kwargs))
                else:
                    urls.append(make_url(manager, c, expire=False))
            return urls