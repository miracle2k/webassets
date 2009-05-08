import tokenize

from django import template
from django_assets.conf import settings
from django_assets.merge import get_merged_url, get_source_urls


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
            if x is None:
                return None
            else:
                return template.Variable(x).resolve(context)
        return _(self.output), [_(f) for f in self.files], _(self.filter)

    def render(self, context):
        output, files, filter = self.resolve(context)

        if not settings.ASSETS_DEBUG:
            merged_url = get_merged_url(files, output, filter)
            if merged_url:
                context.update({'ASSET_URL': merged_url})
                try:
                    result = self.childnodes.render(context)
                finally:
                    context.pop()
                return result

        # At this point, either ASSETS_DEBUG is enabled, or
        # ``get_merged_url`` returned False, in both cases we render
        # the source assets.
        result = u""
        for source in get_source_urls(files):
            context.update({'ASSET_URL': source})
            try:
                result += self.childnodes.render(context)
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
        # Handle separating comma; for backwards-compatibility
        # reasons, this is currently optional, but is enforced by
        # the Jinja extension already.
        if arg[-1] == ',':
            arg = arg[:-1]
            if not arg:
                continue

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



# if Coffin is installed, expose the Jinja2 extension
try:
    from coffin.template import Library as CoffinLibrary
except ImportError:
    register = template.Library()
else:
    register = CoffinLibrary()
    from django_assets.jinja2.extension import AssetsExtension
    register.tag(AssetsExtension)

# expose the default Django tag
register.tag('assets', assets)