from webassets import six

__all__ = 'register_global_renderer', 'BundleRenderer'

global_renderers = dict()


def prepare_renderer(name, renderer, inline_renderer=None):
    '''
    For internal use only -- prepares the renderers to be
    stored in the internal lookup tables.
    '''
    if isinstance(renderer, six.string_types):
        renderer = make_template_renderer(renderer)
    if isinstance(inline_renderer, six.string_types):
        inline_renderer = make_template_renderer(inline_renderer)
    if inline_renderer is None:
        inline_renderer = renderer
    return (renderer, inline_renderer)


def register_global_renderer(name, renderer, inline_renderer=None):
    '''
    Register the `renderer` under the name `name` globally. If
    `inline_renderer` is ``None``, it will default to the using the
    non-inline `renderer`.

    Note that, as always, using globals is usually not a good. It is
    usually a much better idea to register the renderers within the
    specific :class:`webassets.env.Environment` context that they will
    be used (the Environment class has a `register_renderer()` method
    that is perfect for that).

    Renderers can be either a callable or a template string. If they
    are a string, they will be converted to callables by
    :func:`.make_template_renderer`.

    Renderers are called with the following keyword parameters:

    * `bundle`: the Bundle object being rendered.
    * `type`: the renderer type, i.e. the `name`.
    * `url`: the currently being rendered asset URL.
    * `content`: the asset content (for inline renderings only).
    '''
    global_renderers[name] = prepare_renderer(
        name, renderer, inline_renderer)


def make_template_renderer(template):
    '''
    Returns a callable renderer from the provided string `template`.
    The template is assumed to be in `str.format syntax
    <http://docs.python.org/2/library/string.html#formatstrings>`_,
    which has access to all parameters specified in
    :func:`.register_global_renderer` (of which `url` and `content`
    are most interesting).
    '''
    return str(template).format


# register a default renderer that simply outputs the data as-is. not
# particularly useful, but at least that way it is visible, and
# developers will hopefully realize that it is a mis-configuration...

register_global_renderer(None, '{url}', '{content}')

# register some globally useful renderers for css and javascript.

# todo: technically, the `content` should be CDATA-escaped here, but
# that is perhaps a little too much? afterall, the "]]>" sequence in
# css and javascript is pretty rare, i think (i've never seen it)

register_global_renderer(
    'css',
    '<link rel="stylesheet" type="text/css" href="{url}"/>',
    '<style type="text/css"><!--/*--><![CDATA[/*><!--*/\n{content}\n/*]]>*/--></style>')

register_global_renderer(
    'js',
    '<script type="text/javascript" src="{url}"></script>',
    '<script type="text/javascript"><!--//--><![CDATA[//><!--\n{content}\n//--><!]]></script>')

# todo: register renderers for less. the complication with that, is
# that it is sensitive to whether or not the less is compiled
# client-side or server-side...

# # in server-side compiled mode
# register_global_renderer(
#     'less',
#     '<link rel="stylesheet" type="text/css" href="{url}"/>',
#     '<style type="text/css"><!--/*--><![CDATA[/*><!--*/\n{content}\n/*]]>*/--></style>')
# # in client-side compiled mode
# register_global_renderer(
#     'less',
#     '<link rel="stylesheet/less" type="text/css" href="{url}"/>',
#     '<style type="text/less"><!--/*--><![CDATA[/*><!--*/\n{content}\n/*]]>*/--></style>')


class BundleRenderer(object):

    def __init__(self, env, bundle, url, inline):
        self.env    = env
        self.bundle = bundle
        self.url    = url
        self.inline = inline

    def _get_renderer(self, name):
        rend = None
        if hasattr(self.env, 'renderers'):
          rend = self.env.renderers.get(name, None)
        if rend is None:
            rend = global_renderers.get(name, None)
        if rend is None:
            raise ValueError('Cannot find renderer "%s"' % (str(name),))
        return rend

    def render(self, inline=None):
        if inline or ( inline is None and self.inline ):
            return self._render_inline()
        return self._render_ref()

    def _render_ref(self):
        typ  = self.bundle.renderer
        rend = self._get_renderer(typ)[0]
        return rend(
            type=typ, bundle=self.bundle, url=self.url, env=self.env)

    def _render_inline(self):
        typ  = self.bundle.renderer
        rend = self._get_renderer(typ)[1]
        buf  = six.StringIO()
        self.bundle.build(force=True, output=buf, env=self.env)
        buf  = buf.getvalue()
        return rend(
            type=typ, bundle=self.bundle, url=self.url, content=buf, env=self.env)

