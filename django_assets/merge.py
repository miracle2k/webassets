"""Contains the core functionality that manages merging of assets.
"""

import os
import cStringIO as StringIO
import urlparse

from django.utils.datastructures import SortedDict

from django_assets.conf import settings
from django_assets.updater import get_updater
from django_assets.bundle import Bundle, BundleError


__all__ = ('process',)


class MergeError(Exception):
    pass


def absurl(fragment):
    """Create an absolute url based on MEDIA_URL.
    """
    root = settings.MEDIA_URL
    root += root[-1:] != '/' and '/' or ''
    return urlparse.urljoin(root, fragment)


def abspath(filename):
    """Create an absolute path based on MEDIA_ROOT.
    """
    if os.path.isabs(filename):
        return filename
    return os.path.abspath(os.path.join(settings.MEDIA_ROOT, filename))


def process(bundle, force=False, allow_debug=True):
    """Process the given bundle; this includes merging the files
    together and applying filters as appropriate.

    Depending on the given bundle and it's sub-bundles contents,
    as well as the debug setting, the result can be a list of
    urls pointing to source files, urls pointing to generated
    output files, or be stream of in-memory content that contains
    merged/filtered data.

    If ``force`` is given, the asset will be built in any case,
    regardless of whether an update is really necessary.

    ``allow_debug`` is usually used in combination with ``force``.
    It disables debugging, even if the environment is in debug
    mode right now. In other words, it will cause the bundle to
    be processed like in production.
    """

    # STEP 1) Convert into a list of files to generate.
    joblist = bundle_to_joblist(bundle, allow_debug=allow_debug)

    # STEP 2) Optimize that list.
    simplify_jobs(joblist)

    # STEP 3) Ensure all the assets exist, return urls.
    result = []
    for output_path, work in joblist.iteritems():
        if isinstance(work, (tuple, list)):
            build(output_path, work, force=force)
            result.append(make_url(output_path))
        else:
            result.append(make_url(output_path))
    return result


def build(output, worklist, force=False):
    """Given the ``output`` target and the list of things to do,
    first determine if any action is necessary at all (i.e. resource
    may already be built), and if so, build or rebuild the asset.
    """
    # a) Get all files involved (regardless of filters), as absolute paths.
    output_path = abspath(output)
    source_paths = []
    for f, files in worklist:
        source_paths.extend(map(abspath, files))

    # b) Check if the output file needs to be (re)created.
    update_needed = False
    if not os.path.exists(output_path):
        if not settings.ASSETS_AUTO_CREATE or force:
            raise MergeError('\'%s\' needs to be created, but '
                             'ASSETS_AUTO_CREATE is disabled' % output)
        else:
            update_needed = True
    elif not force:
        update_needed = get_updater()(output_path, source_paths)

    # c) If an update is required, build the asset.
    if update_needed or force:
        output = output_path
        try:
            try:
                for filters, files in worklist:
                    output = merge(map(abspath, files), output, filters,
                                   output_path, close=False)
            finally:
                # might still be a string object.
                if hasattr(output, 'close'):
                    output.close()
        except:
            # If there was an error above make sure we delete a possibly
            # partly created output file, or it might be considered "done"
            # from now on.
            if os.path.exists(output_path):
                os.remove(output_path)
            raise


def merge(sources, output, filters, output_path, close=True):
    """The low-level function that actually takes a bunch of files,
    applies filters and merges them together into an output file.

    ``output`` may be a (relative or absolute) path, or a stream. If
    the latter, the actual path still is passed through ``output_path``.
    This is necessary for source filters, who need to kn ow.

    Tries to be efficient by minimizing the number of times the data
    needs to be piped from one stream into another.

    If ``close`` is disabled, returns the output file it is writing to
    without closing it first. The caller can use the received value
    and pass it into the next call to ``merge``, if it needs to place
    multiple pieces of content here.
    """

    # split between output and source filters
    source_attr = 'is_source_filter'
    output_filters = [f for f in filters if not getattr(f, source_attr, False)]
    source_filters = [f for f in filters if getattr(f, source_attr, False)]

    # make paths absolute (they might already be, we can't be sure)
    output_path = abspath(output_path)
    source_paths = [abspath(s) for s in sources]

    # Either open the output file, or simply use the file object
    # that was passed into this function.
    # TODO: is it possible that another simultaneous request might
    # cause trouble? how would we avoid this?
    open_output = lambda: output if hasattr(output, 'write') else open(output_path, 'wb')

    # If no output filters are used, we can write directly to the
    # given target for improved performance.
    buf = (output_filters) and StringIO.StringIO() or open_output()
    result = None
    try:
        for source in source_paths:
            _in = open(source, 'rb')
            try:
                # apply source filters
                if source_filters:
                    tmp_buf = _in  # first filter reads directly from input
                    for filter in source_filters[:-1]:
                        tmp_out = StringIO.StringIO()
                        filter.apply(tmp_buf, tmp_out, source, output_path)
                        tmp_buf = tmp_out
                        tmp_buf.seek(0)
                    # Let last filter write directly to final buffer
                    # for performance, instead of copying once more.
                    for filter in source_filters[-1:]:
                        filter.apply(tmp_buf, buf, source, output_path)
                else:
                    buf.write(_in.read())
                buf.write("\n")  # can be important, depending on content
            finally:
                _in.close()

        # apply output filters, copy from "buf" to "out" (the file)
        if output_filters:
            out = open_output()
            try:
                buf.seek(0)
                for filter in output_filters[:-1]:
                    tmp_out = StringIO.StringIO()
                    filter.apply(buf, tmp_out)
                    buf = tmp_out
                    buf.seek(0)
                # Handle the very last filter separately, let it
                # write directly to output file for performance.
                for filter in output_filters[-1:]:
                    filter.apply(buf, out)
            finally:
                # "out" is the final output file we want to return.
                result = out
                if close:
                    out.close()
                    out = None
    finally:
        # If a result has not been set yet, then "buf" is the
        # final output file.
        if not result:
            result = buf
            if close:
                buf.close()
                buf = None
        else:
            buf.close()
            buf = None

    return result


def make_url(filename):
    """Return a output url, modified for expire header handling.
    """
    path = abspath(filename)
    last_modified = os.stat(path).st_mtime
    if settings.ASSETS_EXPIRE == 'querystring':
        result = "%s?%d" % (filename, last_modified)
    elif settings.ASSETS_EXPIRE == 'filename':
        name = filename.rsplit('.', 1)
        if len(name) > 1:
            result = "%s.%d.%s" % (name[0], last_modified, name[1])
        else:
            result = "%s.%d" % (name, last_modified)
    elif not settings.ASSETS_EXPIRE:
        result = filename
    else:
        raise ValueError('Unknown value for ASSETS_EXPIRE option: %s' %
                            settings.ASSETS_EXPIRE)
    return absurl(result)


def merge_filters(filters1, filters2):
    """Merge two filter lists into one.

    Duplicate filters are removed. Since filter order is important,
    the order of the arguments to this function also matter. Duplicates
    are always removed from the second filter set if they exist in the
    first.

    This function presumes that all the given filters inherit from
    ``Filter``, which properly implements operators to determine
    duplicate filters.
    """
    result = filters1[:]
    for f in filters2:
        if not f in result:
            result.append(f)
    return result


def resolve_action(bundle, default_debug=None, allow_debug=True):
    """Decide what needs to be done for the given bundle.

    Specifically, whether to apply filters and whether to merge. This
    depends on both the global settings (here represented by the
    ``default_debug`` argument), as well as modifiers given by the bundle.

    Returns a 2-tuple of (merge, filter).

    If ``allow_debug`` is False, then we will never be in debug mode.
    """
    if not settings.DEBUG or not allow_debug:
        return True, True

    if default_debug is None:
        default_debug = settings.ASSETS_DEBUG

    debug = bundle.debug if bundle.debug is not None else default_debug

    if debug == 'merge':
        return True, False
    elif debug is True:
        return False, False
    elif debug is False:
        return True, True
    else:
        raise ValueError('Invalid debug value: %s' % debug)


def bundle_to_joblist(bundle, allow_debug=True):
    """Convert the bundle hierarchy into a "job list".

    Each job represents one output url; often there will be only
    a single job, if nested bundles insist on not being merged
    into their parents, there may be multiple ones; direct output
    to memory is a special case of a job.

    After multiple different tries, this "job list" approach
    is the best one I found yet; the most important aspect is that
    when we merge and filter, we always know the final output file,
    and all the source files ultimately involved, even when they
    are handled in a different pass. We need this information for
    example to determine when we need to regenerate at all, or
    when applying source filters.

    Example return:
        'output.js': (
                (('js'), ('file1', 'file2', 'file3', 'file4',)),
                (('js', 'sass'), ('foo', 'bar',)),
                ((), ('no', 'filters', 'applied',)),
            ),
        'link-to-source.js': 'js/link-to-source.js',
    }

    TODO: Consider that the tree:
        csspack (files)
            sass (files
        csspack (files)
    could be more processed with less filter-applications as
        "csspack(files + sass(files) + files))"
    Currently we are in fact doing:
        "csspack(files) + csspack(sass(files)) + csspack(files)"
    """

    jobs = SortedDict()

    def handle(bundle, work_list=[], parent_filters=[], output=False, debug=None):
        do_merge, do_filters = resolve_action(bundle, debug, allow_debug=allow_debug)

        # Merge filtersets with parent.
        sum_filters = parent_filters
        if do_filters and bundle.filters:
            sum_filters = merge_filters(bundle.filters, parent_filters)

        # Determine whether we need to create a new job for this bundle,
        # and if so, where to output to.
        create_needed = False
        if not do_merge:
            output = False
            # This will cause all of this Bundle's contents to end up as
            # their own job, same as if no output were specified.
        elif not output:
            output = bundle.output
            create_needed = True
        else:
            pass # keep

        _files = []

        for c in bundle.contents:
            # Item is a file reference.
            if not isinstance(c, Bundle):
                if not do_merge:
                    # Source the file (add as it's own job)
                    jobs[c] = c
                else:
                    # Collect the file for later.
                    _files.append(c)

            # Item is a Bundle.
            else:
                # Determine how to inherit the debug flag to sub-bundles.
                this_debug = bundle.debug if bundle.debug != None else debug

                if do_merge:
                    # Be sure to process the part of our own content files
                    # that we have collected so far. The subbundle might
                    # need different filters applied, but still needs to
                    # be merged in the proper order.
                    if _files:
                        work_list.append((sum_filters, _files))
                    _files = []
                    # Process the subbundle recursively.
                    handle(c, work_list, sum_filters, output, this_debug)
                else:
                    # Call ourselves recursively without specifying an
                    # output, which will ensure the call creates a new job.
                    handle(c, [], sum_filters, None, this_debug)

        # Process (the rest?) of our collected files.
        if _files:
            work_list.append((sum_filters, _files))

        # If an output job is requested, create one.
        if create_needed:
            if output:
                if output in jobs:
                    raise BundleError('Bundle %s targets the same output file '
                                      'as another bundle: %s' % (bundle, output))
                jobs[output] = work_list[:]
                del work_list[:]
            elif not output and work_list:
                raise BundleError('No output target found for %s' % bundle)

    handle(bundle)
    return jobs


def simplify_jobs(joblist):
    """Take the output of ``bundle_to_joblist``, and further simplify
    it may collapsing multiple steps of a job into a single one
    where possible.

    Why is this necessary? Bundles may be nested inside each other
    without limit. Yet we want to make sure we process a bundle as
    efficiently as possible.

    For example, imagine multiple levels of bundles all applying the
    same filters, with the same settings. It would be a waste of time
    to do this in multiple steps; rather, it makes sense to apply the
    filters in one go to the sum of all content.

    This is not possible if a sub-bundle uses different filters as the
    parent bundle, for example.

    Therefore, what this function does is take the given bundle
    structure and collapse bundles where possible.

    TODO: Implement this. It could also try to partially collapse
    bundles, e.g. a sub-bundle may contain files that can be collapsed,
    but also other bundles that cannot be. Pay attention to ordering
    though: All bundle contents need to add up in the output in the same
    result as in the input. Alternatively, we could add an "unordered"
    attribute to the Bundle class to indicate so. We could have CSSBundle
    and JSBundle subclasses, with the appropriate behavior, respectively.
    Just some ideas, some of this is probably overkill.

    TODO: Do the filters need to match in order? => Probably; maybe
    filters can export that information.
    """
    pass
