======
Jinja2
======

A Jinja2 extension is available as ``webassets.ext.jinja2.AssetsExtension``.
It will provide a ``{% assets %}`` tag which allows you to reference your
bundles from within a template to render its urls.

It also allows you to create bundles on-the-fly, thus making it possible
to define your assets entirly within your templates.

If you are using Jinja2 inside of Django, see
:django:`this page <jinja2>`.


Setting up the extension
------------------------

.. code-block:: python

    from jinja2 import Environment as Jinja2Environment
    from webassets import Environment as AssetsEnvironment
    from webassets.ext.jinja2 import AssetsExtension

    assets_env = AssetsEnvironment('./static/media', '/media')
    jinja2_env = Jinja2Environment(extensions=[AssetsExtension])
    jinja2_env.assets_environment = assets_env

After adding the extension to your Jinja 2 environment, you need to
make sure that it knows about your ``webassets.Environment`` instance.
This is done by setting the ``assets_environment`` attribute.


Using the tag
-------------

To output a bundle that has been registered with the environment, simply
pass its name to the tag:

.. code-block:: jinja

    {% assets "all_js", "ie_js" %}
        <script type="text/javascript" src="{{ ASSET_URL }}"></script>
    {% endassets %}


The tag will repeatedly output its content for each ``ASSET_URL`` of each
bundle. In the above case, that might be the output urls of the *all_js*
and *ie_js* bundles, or, in debug mode, urls referencing the source files
of both bundles.

If you pass something to the tag that isn't a known bundle name, it will
be considered a filename. This allows you to define a bundle entirely
within your templates:

.. code-block:: jinja

    {% assets filters="cssmin,datauri", output="gen/packed.css", "common/jquery.css", "site/base.css", "site/widgets.css" %}
    ...


Of course, this means you can combine the two approaches as well. The
following code snippet will merge together the given bundle and the contents
of the ``jquery.js`` file that was explicitly passed:

.. code-block:: jinja

    {% assets output="gen/packed.js", "common/jquery.js", "my-bundle" %}
    ...

