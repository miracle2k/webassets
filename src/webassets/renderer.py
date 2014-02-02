from webassets import six

from .bundle import Bundle

__all__ = 'register_global_renderer'

global_renderers = dict()

class Renderer(object):
    def __init__(self, reference, inline, mergeable):
        self.reference = reference
        self.inline    = inline
        self.mergeable = mergeable

def prepare_renderer(name, renderer, inline_renderer=None, merge_checker=None):
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
    return Renderer(renderer, inline_renderer, merge_checker)


def register_global_renderer(name, renderer, inline_renderer=None, merge_checker=None):
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
    * `env`: the current environment object.

    The optional parameter `merge_checker` specifies a callable that
    is used when rendering bundles that contain renderers of different
    types. It must return a boolean (mergeable or not mergeable) or
    None (unknown). It is called with the following keyword
    parameters:

    * `parent`: the "parent" (i.e. container bundle) renderer type.
    * `child`: the "child" (i.e. the contained bundle) renderer type.
    * `env`: the current environment object.
    '''
    global_renderers[name] = prepare_renderer(
        name, renderer, inline_renderer, merge_checker)


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


def get_renderer(env, name):
    ret = None
    if hasattr(env, 'renderers'):
        ret = env.renderers.get(name, None)
    if ret is None:
        ret = global_renderers.get(name, None)
    if ret is None:
        raise ValueError('Cannot find renderer "%s"' % (str(name),))
    return ret


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

# register a less renderer
# todo: perhaps this should be registered by the 'less' filter?...

LESS_REFERENCE_FMT = '<link rel="{rel}" type="text/css" href="{url}"/>'
LESS_INLINE_FMT = '''\
<style type="{type}"><!--/*--><![CDATA[/*><!--*/
{content}
/*]]>*/--></style>'''

def less_renderer(type, bundle, url, env, **kw):
    runlessc = not env.debug or env.config.get('less_run_in_debug', True)
    rel = 'stylesheet' if runlessc else 'stylesheet/less'
    return LESS_REFERENCE_FMT.format(rel=rel, url=url)

def less_inline_renderer(type, bundle, url, content, env, **kw):
    runlessc = not env.debug or env.config.get('less_run_in_debug', True)
    type = 'text/css' if runlessc else 'text/less'
    return LESS_INLINE_FMT.format(type=type, content=content)

def less_merge_checker(parent, child, env):
    if parent == 'less' and child == 'css':
        return True
    if parent != 'css' or child != 'less':
        return None
    return not env.debug or env.config.get('less_run_in_debug', True)

register_global_renderer(
    'less', less_renderer, less_inline_renderer, less_merge_checker)


def mergeable_renderer_types(env, parent, child):
    if parent == child: # paranoia
        return True
    mergeable = get_renderer(env, parent).mergeable
    if mergeable is not None:
        ret = mergeable(parent=parent, child=child, env=env)
        if ret is not None:
            return ret
    mergeable = get_renderer(env, child).mergeable
    if mergeable is not None:
        ret = mergeable(parent=parent, child=child, env=env)
        if ret is not None:
            return ret
    return False

def mergeable_renderer(env, bundle, renderer):
    if bundle.renderer is not None and bundle.renderer != renderer:
        return mergeable_renderer_types(env, renderer, bundle.renderer)
    for sub in bundle.contents:
        if isinstance(sub, Bundle):
            if not mergeable_renderer(env, sub, renderer):
                return False
    return True


def bundle_renderer_iter(bundle, env, inline, default, *args, **kwargs):
    default = bundle.renderer or default
    # first, check for mixed-renderer bundles
    if mergeable_renderer(env, bundle, default):
        for bundle, extra_filters in bundle.iterbuild(env):
            for url in bundle._urls(env, extra_filters, *args, **kwargs):
                yield BundleRenderer(env, bundle, url, inline, default)
        return
    def copy(bundle, renderer, index=0):
        ret = Bundle(renderer=renderer)
        # copying all attributes except 'contents' and 'renderer'...
        for attr in ('env', 'output', 'filters', 'debug', \
                     'depends', 'version', 'extra'):
            setattr(ret, attr, getattr(bundle, attr))
        if index != 0:
            # todo: this is a hack. the problem is that when a bundle
            # gets fragmented for multi-renderer support, it needs a
            # different output location...
            if ret.output is None:
                import uuid
                ret.output = 'bundle-fragment-' + str(uuid.uuid4()).replace('-', '')
            ret.output += ':%d' % (index,)
        return (ret, index + 1)
    cur, idx = copy(bundle, default)
    for sub in bundle.contents:
        if not isinstance(sub, Bundle) or mergeable_renderer(env, sub, default):
            if cur is None:
                cur, idx = copy(bundle, default, idx)
            cur.contents += (sub,)
            continue
        if cur and cur.contents:
            for br in bundle_renderer_iter(cur, env, inline, default, *args, **kwargs):
                yield br
        cur = None
        for br in bundle_renderer_iter(sub, env, inline, default, *args, **kwargs):
            yield br
    if cur and cur.contents:
        for br in bundle_renderer_iter(cur, env, inline, default, *args, **kwargs):
            yield br


class BundleRenderer(object):

    def __init__(self, env, bundle, url, inline=None, default=None):
        self.env     = env
        self.bundle  = bundle
        self.url     = url
        self.inline  = inline
        self.default = default

    def render(self, inline=None, default=None):
        if inline or ( inline is None and self.inline ):
            return self._render_inline(default=default or self.default)
        return self._render_ref(default=default or self.default)

    def _render_ref(self, default=None):
        typ  = self.bundle.renderer or default
        return get_renderer(self.env, typ).reference(
            type=typ, bundle=self.bundle, url=self.url, env=self.env)

    def _render_inline(self, default=None):
        typ  = self.bundle.renderer or default
        buf  = six.StringIO()
        self.bundle.build(force=True, output=buf, env=self.env)
        buf  = buf.getvalue()
        return get_renderer(self.env, typ).inline(
            type=typ, bundle=self.bundle, url=self.url, content=buf, env=self.env)

