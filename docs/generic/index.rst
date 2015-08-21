======================================
Using ``webassets`` in standalone mode
======================================

You don't need to use one of the frameworks into which ``webassets`` can
integrate. Using the underlying facilites directly is almost as easy.

And depending on what libraries you use, there may still be some things
*webassets* can help you with, see :doc:`/integration/index`.


Quick Start
-----------

First, create an environment instance:

.. code-block:: python

    from webassets import Environment
    my_env = Environment(
        directory='../static/media',
        url='/media')


As you can see, the environment requires two arguments:

- the path in which your media files are located

- the url prefix under which the media directory is available. This prefix will be used when generating
  output urls.

Next, you need to define your assets, in the form of so called *bundles*,
and register them with the environment. The easiest way to do it is directly
in code:

.. code-block:: python

     from webassets import Bundle
     js = Bundle('common/jquery.js', 'site/base.js', 'site/widgets.js',
                 filters='jsmin', output='gen/packed.js')
     my_env.register('js_all', js)


However, if you prefer, you can of course just as well define your assets
in an external config file, and read them from there. ``webassets``
includes a number of :doc:`helper classes <../loaders>` for some popular
formats like YAML.

Using the bundles
~~~~~~~~~~~~~~~~~

Now with your assets properly defined, you want to merge and minify
them, and include a link to the compressed result in your web page. How
you do this depends a bit on how your site is rendered.

.. code-block:: python

    >>> my_env['js_all'].urls()
    ('/media/gen/packed.js?9ae572c',)

This will always work. You can call your bundle's ``urls()`` method, which
will  automatically merge and compress the source files, and return the
url to the final output file. Or, in debug mode, it would return the urls
of each source file:

.. code-block:: python

    >>> my_env.debug = True
    >>> my_env['js_all'].urls()
    ('/media/common/jquery.js',
     '/media/site/base.js',
     '/media/site/widgets.js',)

Take these urls, pass them to your templates, or otherwise ensure they'll
be used on your website when linking to your Javascript and CSS files.

For some templating languages, ``webassets`` provides extensions to access
your bundles directly within the template. See :doc:`../integration/index` for
more information.


Using the Command Line Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See :doc:`/script`.


Further Reading
---------------

.. toctree::
    :maxdepth: 1

    /environment
    /bundles
    /script
    /builtin_filters
    /custom_filters
    /css_compilers
    /loaders
    /integration/index
    custom_resolver
    /faq
