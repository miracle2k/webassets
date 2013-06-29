import os
from os import path
from webassets import six
from webassets.six.moves import map
from webassets.six.moves import zip

from .filter import get_filter
from .merge import (FileHunk, UrlHunk, FilterTool, merge, merge_filters,
                   select_filters, MoreThanOneFilterError, NoFilters)
from .updater import SKIP_CACHE
from .exceptions import BundleError, BuildError
from .utils import cmp_debug_levels, urlparse


__all__ = ('Bundle', 'get_all_bundle_files',)


def is_url(s):
    if not isinstance(s, str):
        return False
    parsed = urlparse.urlsplit(s)
    return bool(parsed.scheme and parsed.netloc) and len(parsed.scheme) > 1


def has_placeholder(s):
    return '%(version)s' in s


class Bundle(object):
    """A bundle is the unit webassets uses to organize groups of media files,
    which filters to apply and where to store them.

    Bundles can be nested arbitrarily.

    A note on the connection between a bundle and an "environment" instance:
    The bundle requires a environment that it belongs to. Without an
    environment, it lacks information about how to behave, and cannot know
    where relative paths are actually based. However, I don't want to make the
    ``Bundle.__init__`` syntax more complicated than it already is by requiring
    an Environment object to be passed. This would be a particular nuisance
    when nested bundles are used. Further, nested bundles are never explicitly
    connected to an Environment, and what's more, the same child bundle can be
    used in multiple parent bundles.

    This is the reason why basically every method of the Bundle class takes an
    ``env`` parameter - so a parent bundle can provide the environment for
    child bundles that do not know it.
    """

    def __init__(self, *contents, **options):
        self.env = None
        self.contents = contents
        self.output = options.pop('output', None)
        self.filters = options.pop('filters', None)
        self.debug = options.pop('debug', None)
        self.depends = options.pop('depends', [])
        self.version = options.pop('version', [])
        self.extra = options.pop('extra', {})
        if options:
            raise TypeError("got unexpected keyword argument '%s'" %
                            list(options.keys())[0])

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
        """Filters may be specified in a variety of different ways, including
        by giving their name; we need to make sure we resolve everything to an
        actual filter instance.
        """
        if value is None:
            self._filters = ()
            return

        if isinstance(value, six.string_types):
            # 333: Simplify w/o condition?
            if six.PY3:
                filters = map(str.strip, value.split(','))
            else:
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

    def _get_extra(self):
        if not self._extra and not has_files(self):
            # If this bundle has no extra values of it's own, and only
            # wraps child bundles, use the extra values of those.
            result = {}
            for bundle in self.contents:
                if bundle.extra is not None:
                    result.update(bundle.extra)
            return result
        else:
            return self._extra
    def _set_extra(self, value):
        self._extra = value
    extra = property(_get_extra, _set_extra, doc="""A custom user dict of
    extra values attached to this bundle. Those will be available in
    template tags, and can be used to attach things like a CSS
    'media' value.""")

    def resolve_contents(self, env=None, force=False):
        """Return an actual list of source files.

        What the user specifies as the bundle contents cannot be
        processed directly. There may be glob patterns of course. We
        may need to search the load path. It's common for third party
        extensions to provide support for referencing assets spread
        across multiple directories.

        This passes everything through :class:`Environment.resolver`,
        through which this process can be customized.

        At this point, we also validate source paths to complain about
        missing files early.

        The return value is a list of 2-tuples ``(original_item,
        abspath)``. In the case of urls and nested bundles both tuple
        values are the same.

        Set ``force`` to ignore any cache, and always re-resolve
        glob  patterns.
        """
        env = self._get_env(env)

        # TODO: We cache the values, which in theory is problematic, since
        # due to changes in the env object, the result of the globbing may
        # change. Not to mention that a different env object may be passed
        # in. We should find a fix for this.
        if getattr(self, '_resolved_contents', None) is None or force:
            resolved = []
            for item in self.contents:
                try:
                    result = env.resolver.resolve_source(item)
                except IOError as e:
                    raise BundleError(e)
                if not isinstance(result, list):
                    result = [result]

                # Exclude the output file.
                # TODO: This will not work for nested bundle contents. If it
                # doesn't work properly anyway, should be do it in the first
                # place? If there are multiple versions, it will fail as well.
                # TODO: There is also the question whether we can/should
                # exclude glob duplicates.
                if self.output:
                    try:
                        result.remove(self.resolve_output(env))
                    except (ValueError, BundleError):
                        pass

                resolved.extend(map(lambda r: (item, r), result))

            self._resolved_contents = resolved
        return self._resolved_contents

    def _get_depends(self):
        return self._depends
    def _set_depends(self, value):
        self._depends = [value] if isinstance(value, six.string_types) else value
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
            resolved = []
            for item in self.depends:
                try:
                    result = env.resolver.resolve_source(item)
                except IOError as e:
                    raise BundleError(e)
                if not isinstance(result, list):
                    result = [result]
                resolved.extend(result)
            self._resolved_depends = resolved
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
                from .version import VersionIndeterminableError
                if env.versions:
                    try:
                        version = env.versions.determine_version(self, env)
                        assert version
                    except VersionIndeterminableError as e:
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

    def resolve_output(self, env=None, version=None):
        """Return the full, absolute output path.

        If a %(version)s placeholder is used, it is replaced.
        """
        env = self._get_env(env)
        output = env.resolver.resolve_output_to_path(self.output, self)
        if has_placeholder(output):
            output = output % {'version': version or self.get_version(env)}
        return output

    def __hash__(self):
        """This is used to determine when a bundle definition has changed so
        that a rebuild is required.

        The hash therefore should be built upon data that actually affect the
        final build result.
        """
        return hash((tuple(self.contents),
                     self.output,
                     tuple(self.filters),
                     bool(self.debug)))
        # Note how self.depends is not included here. It could be, but we
        # really want this hash to only change for stuff that affects the
        # actual output bytes. Note that modifying depends will be effective
        # after the first rebuild in any case.

    @property
    def is_container(self):
        """Return true if this is a container bundle, that is, a bundle that
        acts only as a container for a number of sub-bundles.

        It must not contain any files of its own, and must have an empty
        ``output`` attribute.
        """
        return not has_files(self) and not self.output

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

        ``parent_debug`` is the debug setting used by the parent bundle. This
        is not necessarily ``bundle.debug``, but rather what the calling method
        in the recursion tree is actually using.

        ``parent_filters`` are what the parent passes along, for us to be
        applied as input filters. Like ``parent_debug``, it is a collection of
        the filters of all parents in the hierarchy.

        ``extra_filters`` may exist if the parent is a container bundle passing
        filters along to its children; these are applied as input and output
        filters (since there is no parent who could do the latter), and they
        are not passed further down the hierarchy (but instead they become part
        of ``parent_filters``.

        ``disable_cache`` is necessary because in some cases, when an external
        bundle dependency has changed, we must not rely on the cache, since the
        cache key is not taking into account changes in those dependencies
        (for now).
        """

        # Determine the debug level to use. It determines if and which filters
        # should be applied.
        #
        # The debug level is inherited (if the parent bundle is merging, a
        # child bundle clearly cannot act in full debug=True mode). Bundles
        # may define a custom ``debug`` attributes, but child bundles may only
        # ever lower it, not increase it.
        #
        # If not parent_debug is given (top level), use the Environment value.
        parent_debug = parent_debug if parent_debug is not None else env.debug
        # Consider bundle's debug attribute and other things
        current_debug_level = _effective_debug_level(
            env, self, extra_filters, default=parent_debug)
        # Special case: If we end up with ``True``, assume ``False`` instead.
        # The alternative would be for the build() method to refuse to work at
        # this point, which seems unnecessarily inconvenient (Instead how it
        # works is that urls() simply doesn't call build() when debugging).
        # Note: This can only happen if the Environment sets debug=True and
        # nothing else overrides it.
        if current_debug_level is True:
            current_debug_level = False

        # Put together a list of filters that we would want to run here.
        # These will be the bundle's filters, and any extra filters given
        # to use if the parent is a container bundle. Note we do not yet
        # include input/open filters pushed down by a parent build iteration.
        filters = merge_filters(self.filters, extra_filters)

        # Initialize the filters. This happens before we choose which of
        # them should actually run, so that Filter.setup() can influence
        # this choice.
        for filter in filters:
            filter.set_environment(env)
            # Since we call this now every single time before the filter
            # is used, we might pass the bundle instance it is going
            # to be used with. For backwards-compatibility reasons, this
            # is problematic. However, by inspecting the support arguments,
            # we can deal with it. We probably then want to deprecate
            # the old syntax before 1.0 (TODO).
            filter.setup()

        # Given the debug level, determine which of the filters want to run
        selected_filters = select_filters(filters, current_debug_level)

        # We construct two lists of filters. The ones we want to use in this
        # iteration, and the ones we want to pass down to child bundles.
        # Why? Say we are in merge mode. Assume an "input()" filter which does
        # not run in merge mode, and a child bundle that switches to
        # debug=False. The child bundle then DOES want to run those input
        # filters, so we do need to pass them.
        filters_to_run = merge_filters(
            selected_filters, select_filters(parent_filters, current_debug_level))
        filters_to_pass_down = merge_filters(filters, parent_filters)

        # Prepare contents
        resolved_contents = self.resolve_contents(env, force=True)

        # Unless we have been told by our caller to use or not use the cache
        # for this, try to decide for ourselves. The issue here is that when a
        # bundle has dependencies, like a sass file with includes otherwise not
        # listed in the bundle sources, a change in such an external include
        # would not influence the cache key, thus the use of the cache causing
        # such a change to be ignored. For now, we simply do not use the cache
        # for any bundle with dependencies. Another option would be to read
        # the contents of all files declared via "depends", and use them as a
        # cache key modifier. For now I am worried about the performance impact.
        #
        # Note: This decision only affects the current bundle instance. Even if
        # dependencies cause us to ignore the cache for this bundle instance,
        # child bundles may still use it!
        actually_skip_cache_here = disable_cache or bool(self.resolve_depends(env))

        filtertool = FilterTool(
            env.cache, no_cache_read=actually_skip_cache_here,
            kwargs={'output': output[0],
                    'output_path': output[1]})

        # Apply input()/open() filters to all the contents.
        hunks = []
        for item, cnt in resolved_contents:
            if isinstance(cnt, Bundle):
                # Recursively process nested bundles.
                hunk = cnt._merge_and_apply(
                    env, output, force, current_debug_level,
                    filters_to_pass_down, disable_cache=disable_cache)
                if hunk is not None:
                    hunks.append((hunk, {}))

            else:
                # Give a filter the chance to open his file.
                try:
                    hunk = filtertool.apply_func(
                        filters_to_run, 'open', [cnt],
                        # Also pass along the original relative path, as
                        # specified by the user, before resolving.
                        kwargs={'source': item},
                        # We still need to open the file ourselves too and use
                        # it's content as part of the cache key, otherwise this
                        # filter application would only be cached by filename,
                        # and changes in the source not detected. The other
                        # option is to not use the cache at all here. Both have
                        # different performance implications, but I'm guessing
                        # that reading and hashing some files unnecessarily
                        # very often is better than running filters
                        # unnecessarily occasionally.
                        cache_key=[FileHunk(cnt)] if not is_url(cnt) else [])
                except MoreThanOneFilterError as e:
                    raise BuildError(e)
                except NoFilters:
                    # Open the file ourselves.
                    if is_url(cnt):
                        hunk = UrlHunk(cnt, env=env)
                    else:
                        hunk = FileHunk(cnt)

                # With the hunk, remember both the original relative
                # path, as specified by the user, and the one that has
                # been resolved to a filesystem location. We'll pass
                # them along to various filter steps.
                item_data = {'source': item, 'source_path': cnt}

                # Run input filters, unless open() told us not to.
                hunk = filtertool.apply(hunk, filters_to_run, 'input',
                                            kwargs=item_data)
                hunks.append((hunk, item_data))

        # If this bundle is empty (if it has nested bundles, they did
        # not yield any hunks either), return None to indicate so.
        if len(hunks) == 0:
            return None

        # Merge the individual files together. There is an optional hook for
        # a filter here, by implementing a concat() method.
        try:
            try:
                final = filtertool.apply_func(filters_to_run, 'concat', [hunks])
            except MoreThanOneFilterError as e:
                raise BuildError(e)
            except NoFilters:
                final = merge([h for h, _ in hunks])
        except IOError as e:
            # IOErrors can be raised here if hunks are loaded for the
            # first time. TODO: IOErrors can also be raised when
            # a file is read during the filter-apply phase, but we don't
            # convert it to a BuildError there...
            raise BuildError(e)

        # Apply output filters.
        # TODO: So far, all the situations where bundle dependencies are
        # used/useful, are based on input filters having those dependencies. Is
        # it even required to consider them here with respect to the cache? We
        # might be able to run this operation with the cache on (the FilterTool
        # being possibly configured with cache reads off).
        return filtertool.apply(final, selected_filters, 'output')

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

        A ``FileHunk`` will be returned, or in a certain case, with no updater
        defined and force=False, the return value may be ``False``.

        TODO: Support locking. When called from inside a template tag, this
        should lock, so that multiple requests don't all start to build. When
        called from the command line, there is no need to lock.
        """

        if not self.output:
            raise BuildError('No output target found for %s' % self)

        # Determine if we really need to build, or if the output file
        # already exists and nothing has changed.
        if force:
            update_needed = True
        elif not has_placeholder(self.output) and \
                not path.exists(self.resolve_output(env, self.output)):
            update_needed = True
        else:
            update_needed = env.updater.needs_rebuild(self, env) \
                if env.updater else True
            if update_needed==SKIP_CACHE:
                disable_cache = True

        if not update_needed:
            # We can simply return the existing output file
            return FileHunk(self.resolve_output(env, self.output))

        hunk = self._merge_and_apply(
            env, [self.output, self.resolve_output(env, version='?')],
            force, disable_cache=disable_cache, extra_filters=extra_filters)
        if hunk is None:
            raise BuildError('Nothing to build for %s, is empty' % self)

        if output:
            # If we are given a stream, just write to it.
            output.write(hunk.data())
        else:
            if has_placeholder(self.output) and not env.versions:
                raise BuildError((
                    'You have not set the "versions" option, but %s '
                    'uses a version placeholder in the output target'
                        % self))

            version = None
            if env.versions:
                version = env.versions.determine_version(self, env, hunk)

            output_filename = self.resolve_output(env, version=version)

            # If it doesn't exist yet, create the target directory.
            output_dir = path.dirname(output_filename)
            if not path.exists(output_dir):
                os.makedirs(output_dir)

            hunk.save(output_filename)
            self.version = version

            if env.manifest:
                env.manifest.remember(self, env, version)
            if env.versions and version:
                # Hook for the versioner (for example set the timestamp of
                # the file) to the actual version.
                env.versions.set_version(self, env, output_filename, version)

        # The updater may need to know this bundle exists and how it
        # has been last built, in order to detect changes in the
        # bundle definition, like new source files.
        if env.updater:
            env.updater.build_done(self, env)

        return hunk

    def build(self, env=None, force=None, output=None, disable_cache=None):
        """Build this bundle, meaning create the file given by the ``output``
        attribute, applying the configured filters etc.

        If the bundle is a container bundle, then multiple files will be built.

        Unless ``force`` is given, the configured ``updater`` will be used to
        check whether a build is even necessary.

        If ``output`` is a file object, the result will be written to it rather
        than to the filesystem.

        The return value is a list of ``FileHunk`` objects, one for each bundle
        that was built.
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

        This will often only entail ``self``, though for container bundles (and
        container bundle hierarchies), a list of all the non-container leafs
        will be yielded.

        Essentially, what this does is "skip" bundles which do not need to be
        built on their own (container bundles), and gives the caller the child
        bundles instead.

        The return values are 2-tuples of (bundle, filter_list), with the
        second item being a list of filters that the parent "container bundles"
        this method is processing are passing down to the children.
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

    def _make_output_url(self, env):
        """Return the output url, modified for expire header handling.
        """

        # Only query the version if we need to for performance
        version = None
        if has_placeholder(self.output) or env.url_expire != False:
            # If auto-build is enabled, we must not use a cached version
            # value, or we might serve old versions.
            version = self.get_version(env, refresh=env.auto_build)

        url = self.output
        if has_placeholder(url):
            url = url % {'version': version}
        url = env.resolver.resolve_output_to_url(url)

        if env.url_expire or (
                env.url_expire is None and not has_placeholder(self.output)):
            url = "%s?%s" % (url, version)
        return url

    def _urls(self, env, extra_filters, *args, **kwargs):
        """Return a list of urls for this bundle, and all subbundles,
        and, when it becomes necessary, start a build process.
        """

        # Look at the debug value to see if this bundle should return the
        # source urls (in debug mode), or a single url of the bundle in built
        # form. Once a bundle needs to be built, all of it's child bundles
        # are built as well of course, so at this point we leave the urls()
        # recursion and start a build() recursion.
        debug = _effective_debug_level(env, self, extra_filters)
        if debug == 'merge':
            supposed_to_merge = True
        elif debug is True:
            supposed_to_merge = False
        elif debug is False:
            supposed_to_merge = True
        else:
            raise BundleError('Invalid debug value: %s' % debug)

        # We will output a single url for this bundle unless a) the
        # configuration tells us to output the source urls
        # ("supposed_to_merge"), or b) this bundle isn't actually configured to
        # be built, that is, has no filters and no output target.
        if supposed_to_merge and (self.filters or self.output):
            # With ``auto_build``, build the bundle to make sure the output is
            # up to date; otherwise, we just assume the file already exists.
            # (not wasting any IO ops)
            if env.auto_build:
                self._build(env, extra_filters=extra_filters, force=False,
                            *args, **kwargs)
            return [self._make_output_url(env)]
        else:
            # We either have no files (nothing to build), or we are
            # in debug mode: Instead of building the bundle, we
            # source all contents instead.
            urls = []
            for org, cnt in self.resolve_contents(env):
                if isinstance(cnt, Bundle):
                    urls.extend(org.urls(env, *args, **kwargs))
                elif is_url(cnt):
                    urls.append(cnt)
                else:
                    try:
                        url = env.resolver.resolve_source_to_url(cnt, org)
                    except ValueError:
                        # If we cannot generate a url to a path outside the
                        # media directory. So if that happens, we copy the
                        # file into the media directory.
                        external = pull_external(env, cnt)
                        url = env.resolver.resolve_source_to_url(external, org)

                    urls.append(url)
            return urls

    def urls(self, env=None, *args, **kwargs):
        """Return a list of urls for this bundle.

        Depending on the environment and given options, this may be a single
        url (likely the case in production mode), or many urls (when we source
        the original media files in DEBUG mode).

        Insofar necessary, this will automatically create or update the files
        behind these urls.
        """
        env = self._get_env(env)
        urls = []
        for bundle, extra_filters in self.iterbuild(env):
            urls.extend(bundle._urls(env, extra_filters, *args, **kwargs))
        return urls


def pull_external(env, filename):
    """Helper which will pull ``filename`` into
    :attr:`Environment.directory`, for the purposes of being able to
    generate a url for it.
    """

    # Generate the target filename. Use a hash to keep it unique and short,
    # but attach the base filename for readability.
    # The bit-shifting rids us of ugly leading - characters.
    hashed_filename = hash(filename) & ((1<<64)-1)
    rel_path = path.join('webassets-external',
        "%s_%s" % (hashed_filename, path.basename(filename)))
    full_path = path.join(env.directory, rel_path)

    # Copy the file if necessary
    if path.isfile(full_path):
        gs = lambda p: os.stat(p).st_mtime
        if gs(full_path) > gs(filename):
            return full_path
    directory = path.dirname(full_path)
    if not path.exists(directory):
        os.makedirs(directory)
    FileHunk(filename).save(full_path)
    return full_path


def get_all_bundle_files(bundle, env=None):
    """Return a flattened list of all source files of the given bundle, all
    its dependencies, recursively for all nested bundles.

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


def _effective_debug_level(env, bundle, extra_filters=None, default=None):
    """This is a helper used both in the urls() and the build() recursions.

    It returns the debug level that this bundle, in a tree structure
    of bundles, should use. It looks at any bundle-specific ``debug``
    attribute, considers an automatic upgrade to "merge" due to filters that
    are present, and will finally use the value in the ``default`` argument,
    which in turn defaults to ``env.debug``.

    It also ensures our rule that in a bundle hierarchy, the debug level may
    only ever be lowered. Nested bundle may lower the level from ``True`` to
    ``"merge"`` to ``False``, but never in the other direction. Which makes
    sense: If a bundle is already being merged, we cannot start exposing the
    source urls a child bundle, not if the correct order should be maintained.

    And while in theory it would seem possible to switch between full-out
    production (debug=False) and ``"merge"``, the complexity there, in
    particular with view as to how certain filter types like input() and
    open() need to be applied to child bundles, is just not worth it.
    """
    if default is None:
        default = env.debug

    if bundle.debug is not None:
        level = bundle.debug
    else:
        # If bundle doesn't force a level, then the presence of filters which
        # declare they should always run puts the bundle automatically in
        # merge mode.
        filters = merge_filters(bundle.filters, extra_filters)
        level = 'merge' if select_filters(filters, True) else None

    if level is not None:
        # The new level must be lower than the older one. We do not thrown an
        # error if this is NOT the case, but silently ignore it. This is so
        # that a debug=True can be used to overwrite auto_debug_upgrade.
        # Otherwise debug=True would always fail.
        if cmp_debug_levels(default, level) > 0:
            return level
    return default


has_files = lambda bundle: \
                any([c for c in bundle.contents if not isinstance(c, Bundle)])
