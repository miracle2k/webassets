"""Contains the core functionality that manages merging of assets.
"""

import os
import cStringIO as StringIO
import urlparse

from django_assets.conf import settings
from django_assets.updater import get_updater
from django_assets.filter import get_filter


__all__ = ('get_source_urls', 'get_merged_url',)


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


def merge(sources, output, filter):
    """Merge multiple source files into the output file, while applying
    the specified filter. Uses an existing output file whenever possible.

    The ``output_path`` and ``source_paths`` arguments can be relative, or
    absolute, we handle both.
    """

    # fail early by resolving filters now (there can be multiple)
    if settings.ASSETS_DEBUG == 'nofilter':
        filters = []
    else:
        if isinstance(filter, basestring):
            filters = filter.split(',')
        else:
            filters = filter and filter or []
        filters = [get_filter(f) for f in filters]
    # split between output and source filters
    source_attr = 'is_source_filter'
    output_filters = [f for f in filters if not getattr(f, source_attr, False)]
    source_filters = [f for f in filters if getattr(f, source_attr, False)]

    # make paths absolute (they might already be, we can't be sure)
    output_path = abspath(output)
    source_paths = [abspath(s) for s in sources]

    # TODO: is it possible that another simultaneous request might
    # cause trouble? how would we avoid this?
    open_output = lambda: open(output_path, 'wb')

    # If no output filters are used, we can write directly to the
    # disk for improved performance.
    buf = (output_filters) and StringIO.StringIO() or open_output()
    try:
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
                    out.close()
        finally:
            buf.close()
    except Exception:
        # If there was an error above make sure we delete a possibly
        # partly created output file, or it might be considered "done"
        # from now on.
        if os.path.exists(output_path):
            os.remove(output_path)
        raise


def get_merged_url(files, output, filter):
    """Return a URL to the merged and filtered version of the given
    files. In certain cases, the return value can also be ``False``.

    If necessary, this will merge ``files``, and apply ``filters``. If
    possible, an existing resource will be reused, so that the asset is
    only rebuild, for example, if any of the source files has changed.
    Various settings effect how this is determined.

    Also depending on the active Django settings, the returned url will
    contain an identifier to break any possible "far future expires"
    headers.

    Note that in certain circumstances the return value can be
    ``False``. This happens when the asset has never been previously
    created and ASSETS_AUTO_CREATE is not enabled. The caller will need
    to handle this situation, possible by falling back to working with
    the individual source files.
    """

    # make paths absolute
    output_path = abspath(output)
    source_paths = [abspath(s) for s in files]

    # check if the asset should be (re)created
    if not os.path.exists(output_path):
        if not settings.ASSETS_AUTO_CREATE:
            return False
        else:
            update_needed = True
    else:
        update_needed = get_updater()(output_path, source_paths)

    if update_needed:
        merge(source_paths, output_path, filter)

    # return a output url, modified for expire header handling
    last_modified = os.stat(output_path).st_mtime
    if settings.ASSETS_EXPIRE == 'querystring':
        result = "%s?%d" % (output, last_modified)
    elif settings.ASSETS_EXPIRE == 'filename':
        name = output.rsplit('.', 1)
        if len(name) > 1:
            result = "%s.%d.%s" % (name[0], last_modified, name[1])
        else:
            result = "%s.%d" % (name, last_modified)
    elif not settings.ASSETS_EXPIRE:
        result = output
    else:
        raise ValueError('Unknown value for ASSETS_EXPIRE option: %s' %
                            settings.ASSETS_EXPIRE)
    return absurl(result)


def get_source_urls(files):
    """Return URLs to the source files given in ``files``.

    This is a sibling to ``get_merged_url`` and would be used in
    debug scenarios where asset management is supposed to be disabled.
    """
    result = []
    for f in files:
        result.append(absurl(f))
    return result