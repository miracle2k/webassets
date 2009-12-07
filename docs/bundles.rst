-------
Bundles
-------

A bundle is simply a collection of files that you would like to group
together, with some properties attached to tell ``django-assets``
how to do it's job. Such properties include the filters which should
be applied, or the location where the output file should be stored.

Depending on how you choose to use ``django-assets``, you will or will
not deal with them directly.

Note that all currently all filenames and paths are considered to be
relative to Django's ``MEDIA_ROOT`` settings, and generated urls will
be based on ``MEDIA_URL``.


Defining assets in code
-----------------------

The most flexible way to declare your bundles is in your application
code:

.. code-block:: python

    from django_assets import Bundle, register

    ie_js_bundle = Bundle('common/libs/flot/excanvas.js',
                          output='gen/packed.ie.js')
    register('ie_js', ie_js_bundle)

    register('all_js',
             # jQuery
             Bundle('common/libs/jquery/jquery.js',
                    'common/libs/jquery/jquery.ajaxQueue.js',
                    'common/libs/jquery/jquery.bgiframe.js',),
             # jQuery Tools
             Bundle('common/libs/jqtools/tools.tabs.js',
                    'common/libs/jqtools/tools.tabs.history.js',
                    'common/libs/jqtools/tools.tabs.slideshow.js'),
             # Our own stuff
             Bundle('common/inheritance.js', 'portal/js/common.js',
                    'portal/js/plot.js', 'portal/js/ticker.js'),
             filter='jsmin',
             output='gen/packed.js')

**Note:** You need to save the above in a file named ``assets.py`` in your
project directory. True to Django style, ``django-assets`` will load
and inspect those automatically, ensuring the ``register`` calls have
executed. Otherwise, you'll need to make sure the registration happens
yourself.

``register`` makes a bundle know to the system under the name given as
the first argument, so that you can later refer to it. The first call
shows the explicit form; the second use of register in the example above
skips the step of defining the bundle explicitly, and simply defines the
bundle inline as part of the ``register`` call itself.

When defining a bundle, apart from any number of source files, some of
the arguments that can be given are:

* ``output``:
    Name/path of the output file. All source files will be merged and the
    result stored at this location.
* ``filters``:
    One or multiple filters to apply. This argument is optional - if no
    filters are specified, the source files will merely be merged into the
    output file.

The use of nested ``Bundle`` objects to group the JavaScript files
together is purely aesthetical. You could just as well pass all files as
a flat list.

Once your bundles are registered with a name, you can refer to them
in your templates:

.. code-block:: django

    {% assets "all_js", "ie_js" %}
        <script type="text/javascript" src="{{ ASSET_URL }}"></script>
    {% endassets %}

This might seem somewhat verbose, but gives you full control over the
HTML that you output, and will allow us to easily render the proper url
to the merged bundle in production, and the individual source urls
while debugging.


Defining assets inside templates
--------------------------------

If you prefer, particularly in simple cases you, you can just skip the
``assets.py`` file, and define your assets directly inside your templates.

Just give the same data you would pass to a bundle to the template tag:

.. code-block:: django

    {% assets filter="jsmin,gzip", output="gen/packed.js", "common/jquery.js", "site/base.js", "site/widgets.js" %}
    ...

As you can see, you can even specify multiple filters, separated by commas.

Internally, ``django-assets`` is simply created a bundle "on-the-fly"
here, which means...


Combining the two approaches
----------------------------

... that you can easily do both. The following code snippet will merge
together the given bundle and the contents of the ``jquery.js`` file
that was explicitly passed:

.. code-block:: django

    {% assets output="gen/packed.js", "common/jquery.js", "my-bundle" %}
    ...


Nesting bundles
---------------

Bundles can be arbitrarily nested, i.e. a bundle may contain another
bundle may contain another bundle. When it comes time to write a bundle
to a file, the hierarchy is flatted. This works mostly how you would
expect. Some things to mention are:

* Filters are merged together, duplicates are removed. The leaf filters
  are applied first.
* An ``output`` option set on a sub-bundle is normally ignored; but see
  the section on CSS compilers below.
* If a bundle that is supposed to be processed to a file does not define
  an output target, it simply serves as a container of it's sub-bundles,
  which in turn will be processed into their respective output files.
  In this case it must not have any files of it's own.
* If a bundle has no files of it's own, but sub-bundles, but defines
  filters, it basically serves the purpose of injecting those filters
  into it's sub-bundles.

What is it good for? Generally, if you have to apply different sets of
filters to different groups of files, but still merge them all together
into a single output file.

In the following some specific examples.

.. _bundles-css_compilers:

CSS compilers
~~~~~~~~~~~~~

CSS Compilers like `CleverCSS <http://sandbox.pocoo.org/clevercss/>`_ or
`less <http://lesscss.org/>`_ differ from most others in that their source
files are not usable in a web browser at all without being first converted.
This conflicts with ``django-assets``'s debug mode: Ideally, while
developing, you would like to have your source files available
uncompressed, so you can actually see what generated code you are working
with.

Enabling debugging mode would disable the CSS compilation; Disabling
debugging would apply the compression. Using a simple ``if-else`` when
defining your bundles will not suffice for all cases. Once you need to
merge raw CSS files and compiled CSS files together, you need to start
using nested bundles:

.. code-block:: python

    less = Bundle('css/base.less', 'css/forms.less',
    	          filters='less', output='gen/less.css',
                  debug=False)
    register('all-css',
             less, 'css/jquery.calendar.css',
             filters='yui_css', output="gen/all.css")

The magic here is in the ``debug`` argument passed the the ``less``
bundle. It takes the same values as the
:ref:`ASSETS_DEBUG <settings-ASSETS_DEBUG>` setting (``True``, ``False``
and ``"merge"`` - in fact, the setting
is simply the default value for that parameter).
By way of this parameter, you specify how this particular bundle should
be processed *while in debug mode* (i.e., it has no effect when running
in production mode).

Setting ``debug`` to ``False`` for the `less`` bundle means that even
when the rest of the system is in debug mode, and no filters will be
applied, this bundle is not: the less files will also be compiled.


Pre-compressed files
~~~~~~~~~~~~~~~~~~~~

If you are using a JavaScript library like `jQuery <http://jquery.com/>`_,
you might find yourself with a file like ``jquery.min.js`` in your media
directory, i.e. it is already minified - no reason to do it again.

While I would recommend always using the raw source files, and letting
``django-assets`` do the compressing, if you do have minified files
that you need to merge together with uncompressed ones, you can use
nested bundles:

.. code-block:: python

	register('js-all',
	         'jquery.min.js',
	         Bundle(filter='jsmin', 'uncompressed.js'))


A note on ordering
~~~~~~~~~~~~~~~~~~

Because in most file types ``django-assets`` deals with (CSS, JavaScript)
order is very significant, the order in which files are defined and
bundles nested is significant as well. This means that you can in some
cases gain performance (not that it usually matters) by checking if it's
possible to optimize the order in which you define your bundles:

.. code-block:: python

	register('css-all',
	         Bundle(filter='cssutils', ...),       # (1)
	         Bundle(filter='less,cssutils', ...),  # (2)
	         Bundle(filter='cssutils', ...),       # (3)

In the above case, ``django-assets`` must apply the ``cssutils`` filter
three separate times, because it is not smart enough to see it can process
the less filter of ``(2)`` first. If the order is not relevant in this case,
one could change the order to ``(1)(3)(2)``, and reduce the number of
``cssutils`` runs by one.
