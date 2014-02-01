.. _renderer:

=================
Rendering Control
=================

Webassets primarily deals with how to generate, compile, filter, and
deploy web assets themselves. However, it can also help with rendering
the asset references, such as the "<link>" and "<script>" tags in
HTML. To leverage that, use the `Bundle` class' ``renderers()``
method, which returns a `BundleRenderer` and the `Environment` class'
``register_renderer()`` method to register custom renderers.


Bundle Rendering
================

Bundles have a method ``.renderers()`` that returns a generator of one
or more BundleRenderers that manage the rendering. The primary method
of a BundleRenderer is the ``.render()`` method, which actually
returns the rendered result.

Renderers are inherited by child bundles from parent bundles if their
renderer is set to ``None``. Note that renderers do not propagate from
child bundles to parent (container) bundles.

Both the ``Bundle.renderers()`` and ``BundleRenderer.render()`` methods
take the following optional parameters:

* `inline`: whether or not to render a reference to the asset as or to
  to inline the asset directly. Note that some renderers can only do
  one or the other.

* `default`: specify a default renderer that is inherited down the
  bundle container stack.

If not renderer is defined or inherited, then the default renderer is
used, which simply renders the asset URL (when referenced) or the
asset contents (when inlined).

For example, to render a CSS link reference or inline stylesheet, you
can do the following:

.. code-block:: python

    >>> bundle = Bundle('style.css', output='app.css', renderer='css')

    # we know that this bundle will only have one renderer...
    >>> renderer = list(bundle.renderers())[0]

    >>> print renderer.render()
    <link rel="stylesheet" type="text/css" href="/app.css"/>

    >>> print renderer.render(inline=True)
    <style type="text/css"><!--/*--><![CDATA[/*><!--*/
    .redish { color: #f30; }
    /*]]>*/--></style>


This is most useful when rendering assets of different types in
templates. For example, with the following environment:

.. code-block:: python

    # creating a bundle with all assets

    all_assets = Bundle(
       Bundle('style.css', output='app.css', renderer='css'),
       Bundle('script.js', output='app.js', renderer='js'),
       )

    env.register('app', all_assets)


Then, in a Mako template:

.. code-block:: mako

    <html>
      <head>
        % for asset in my_webassets_env['app'].renderers():
          ${asset.render()|n}
        % endfor
      </head>
      ...
    </html>


Would generate something like the following output:

.. code-block::

    <html>
      <head>
        <link rel="stylesheet" type="text/css" href="/app.css"/>
        <script type="text/javascript" src="/app.js"></script>
      </head>
      ...
    </html>


Renderer Registration
=====================

Webassets provides default renderers for CSS (named ``"css"``),
JavaScript (named ``"js"``), and LESS CSS (named ``"less"``). If you
need to add more renderers, or change the default rendering, this can
be done via renderer registration.

A renderer is either a string in `str.format syntax
<http://docs.python.org/2/library/string.html#formatstrings>`_,
or a callable that receives the following keyword arguments:

* `type`: the renderer type, i.e. the `name`.
* `bundle`: the Bundle object being rendered.
* `url`: the currently being rendered asset URL.
* `content`: the asset content (for inline renderings only).
* `env`: the environment currently in effect for the rendering.

An example custom ``svg`` renderer that can handle SVG being
rasterized either client-side or server-side (note that this assumes
that there is a filter that rasterizes SVGs to PNGs running that is
sensitive to the `debug` and `svg_run_in_debug` flags):

.. code-block:: python

    def my_svg_renderer(type, bundle, url):
        return '<img src="{url}"/>'

    def my_svg_inline_renderer(type, bundle, url, content):
        from base64 import b64encode
        dosvgc = not bundle.env.debug or bundle.env.config.get('svg_run_in_debug')
        type = 'image/png' if dosvgc else 'image/svg'
        return '<img src="data:{type};base64,{content}"/>'.format(type=type, content=content)


You can register renderers in particular ``Environment`` objects
(recommended) or you can also register renderers globally (only
recommended in rare situations).

To register the renderer in an environment:

.. code-block:: python

    env.register_renderer('svg', my_svg_renderer, my_svg_inline_renderer)


And to register the renderer globally (usually not recommended):

.. code-block:: python

    from webassets.renderer import register_global_renderer
    register_global_renderer('svg', my_svg_renderer, my_svg_inline_renderer)

Note that in the above examples, we registered both a referencing
renderer as well as an inline renderer. If we had specified only the
former, then the inline renderer would default to that one as well.

And here an example of registering a simpler string-based renderer
(but which will always render a reference to the image even when
inlining is requested):

.. code-block:: python

    env.register_renderer(

      # the name of the renderer:
      'svg',

      # the "by reference" rendering:
      '<img src="{url}"/>'

      # an "inline" renderer is not specified, so it will
      # default to the above "by reference" renderer
    )
