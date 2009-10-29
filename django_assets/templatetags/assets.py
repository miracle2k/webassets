import tokenize

from django import template
from django_assets.conf import settings
from django_assets.merge import process
from django_assets.bundle import Bundle


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
        return Bundle(*[_(f) for f in self.files],
                      **{'output': _(self.output), 'filters': _(self.filter)})

    def render(self, context):
        bundle = self.resolve(context)

        result = u""
        for url in process(bundle):
            context.update({'ASSET_URL': url})
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