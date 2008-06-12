import os
import tokenize
import cStringIO as StringIO
import urlparse
from django import template
from django_assets.conf import settings
from django_assets.updater import get_updater
from django_assets.filter import get_filter
from django_assets.tracker import get_tracker

def _absurl(fragment):
    """Create an absolute url based on MEDIA_URL."""
    root = settings.MEDIA_URL
    root += root[-1:] != '/' and '/' or ''
    return urlparse.urljoin(root, fragment)

def _abspath(filename):
    """Create an absolute path based on MEDIA_ROOT."""
    if os.path.isabs(filename):
        return filename
    return os.path.join(settings.MEDIA_ROOT, filename)

def create_merged(sources, output, filter):
    """Does the templatetag's heavy lifting: Merges multiple source files
    into the output file, while applying the specified filter. Uses an
    existing output file whenever possible.

    The ``output_path`` and ``source_paths`` arguments can be relative, or
    absolute, we handle both.
    """

    # fail early by resolving filters now (there can be multiple)
    if settings.ASSETS_DEBUG == 'nofilter':
        filters = []
    else:
        filters = filter and filter.split(',') or []
        filters = [get_filter(f) for f in filters]
    # split between output and source filters
    output_filters = [f for f in filters if not getattr(f, 'is_source_filter', False)]
    source_filters = [f for f in filters if getattr(f, 'is_source_filter', False)]

    # make paths absolute (they might already be, we can't be sure)
    output_path = _abspath(output)
    source_paths = [_abspath(s) for s in sources]

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


class AssetsNode(template.Node):
    def __init__(self, filter, output, files, childnodes):
        self.childnodes = childnodes
        self.output = output
        self.files = files
        self.filter = filter

    def resolve(self, context={}):
        """We allow variables to be used for all arguments; this function
        resolves all data against a given context;

        This is a separate method as the management command must have
        the ability to check if the tag can be resolved without a context.
        """
        def _(x):
            if x is None: return None
            else: return template.Variable(x).resolve(context)
        return _(self.output), [_(f) for f in self.files], _(self.filter)

    def render(self, context):
        if settings.ASSETS_DEBUG:  # includes 'nomerge'
            return self.render_sources(context)
        else:
            return self.render_merged(context)

    def render_sources(self, context):
        """Output the unmodified source files."""
        _, sources, _ = self.resolve(context)
        result = u""
        for source in sources:
            context.update({'ASSET_URL': _absurl(source)})
            try:
                result += self.childnodes.render(context)
            finally:
                context.pop()
        return result

    def render_merged(self, context):
        """Create and output a merged version of all sources."""

        output, files, filter = self.resolve(context)

        # make paths absolute
        output_path = _abspath(output)
        source_paths = [_abspath(s) for s in files]

        # check if the asset should be (re)created
        if not os.path.exists(output_path):
            if not settings.ASSETS_AUTO_CREATE:
                # render the sources after all
                return self.render_sources(context)
            else:
                update_needed = True
        else:
            update_needed = get_updater()(output_path, source_paths)

        if update_needed:
            create_merged(source_paths, output_path, filter)
        last_modified = os.stat(output_path).st_mtime
        # TODO: do asset tracking here
        #get_tracker()()

        # modify the output url for expire header handling
        if settings.ASSETS_EXPIRE == 'querystring':
            outputfile = "%s?%d" % (output, last_modified)
        elif settings.ASSETS_EXPIRE == 'filename':
            name = output.rsplit('.', 1)
            if len(name) > 1: return "%s.%d.%s" % (name[0], last_modified, name[1])
            else: outputfile = "%s.%d" % (name, last_modified)
        elif not settings.ASSETS_EXPIRE:
            outputfile = output
        else:
            raise ValueError('Unknown value for ASSETS_EXPIRE option: %s' %
                                settings.ASSETS_EXPIRE)

        context.update({'ASSET_URL': _absurl(outputfile)})
        try:
            result = self.childnodes.render(context)
        finally:
            context.pop()
        return result


def assets(parser, token):
    filter = None
    output = None
    files = []

    # parse the arguments
    args = token.split_contents()[1:]
    for arg in args:
        # determine if keyword or positional argument
        arg = arg.split('=', 1)
        if len(arg) == 1:
            name = None
            value = arg[0]
        else:
            name, value = arg

        # handle known keyword arguments
        if name == 'output':
            output = value
        elif name == 'filter':
            filter = value
        # positional arguments are source files
        elif name is None:
            files.append(value)
        else:
            raise template.TemplateSyntaxError('Unsupported keyword argument "%s"'%name)

    # checking for missing arguments now means we'll never have to do it again
    if not output:
        raise template.TemplateSyntaxError('Argument "output" is required but missing.')

    # capture until closing tag
    childnodes = parser.parse(("endassets",))
    parser.delete_first_token()
    return AssetsNode(filter, output, files, childnodes)

register = template.Library()
register.tag('assets', assets)