.. _bundles:

=======
Bundles
=======

A bundle is simply a collection of files that you would like to group
together, with some properties attached to tell ``webassets``
how to do its job. Such properties include the filters which should
be applied, or the location where the output file should be stored.

Note that all filenames and paths considered to be relative to the
``directory`` setting of your :doc:`environment <environment>`, and
generated urls will be relative to the ``url`` setting.

.. code-block:: python

    Bundle('common/inheritance.js', 'portal/js/common.js',
           'portal/js/plot.js', 'portal/js/ticker.js',
           filters='jsmin',
           output='gen/packed.js')

A bundle takes any number of filenames, as well as the following keyword
arguments:

* ``filters`` -
  One or multiple filters to apply. If no filters are specified, the
  source files will merely be merged into the output file. Filters are
  applied in the order in which they are given.

* ``output`` - Name/path of the output file. All source files will be merged
  and the result stored at this location. A ``%(version)s`` placeholder is
  supported here, which will be replaced with the version of the file. See
  :doc:`/expiring`.

* ``depends`` - Additional files that will be watched to determine if the 
  bundle needs to be rebuilt. This is usually necessary if you are using
  compilers that allow ``@import`` instructions. Commonly, one would use a
  glob instruction here for simplicity::

    Bundle(depends=('**/*.scss'))

  .. warning::
    Currently, using ``depends`` disables caching for a bundle.


Nested bundles
--------------

Bundles may also contain other bundles:

.. code-block:: python

    from webassets import Bundle

    all_js = Bundle(
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
        filters='jsmin',
        output='gen/packed.js')


Here, the use of nested ``Bundle`` objects to group the JavaScript files
together is purely aesthetical. You could just as well pass all files as
a flat list. However, there are some more serious application as well.
One of them is the use of :doc:`CSS compilers <../css_compilers>`.
Another would be dealing with pre-compressed files:

If you are using a JavaScript library like `jQuery <http://jquery.com/>`_,
you might find yourself with a file like ``jquery.min.js`` in your media
directory, i.e. it is already minified - no reason to do it again.

While I would recommend always using the raw source files, and letting
``webassets`` do the compressing, if you do have minified files that you
need to merge together with uncompressed ones, you could do it like so:

.. code-block:: python

    register('js-all',
        'jquery.min.js',
        Bundle(filters='jsmin', 'uncompressed.js'))


Generally speaking, nested bundles allow you to apply different sets of
filters to different groups of files, but still everything together
into a single output file.

Some things to consider when nesting bundles:

* Duplicate filters are only applied once (the leaf filter is applied).
* If a bundle that is supposed to be processed to a file does not define
  an output target, it simply serves as a container of its sub-bundles,
  which in turn will be processed into their respective output files.
  In this case it must not have any files of its own.


Building bundles
----------------

Once a bundle is defined, the thing you want to do is build it, and then
include a link to the final merged and compressed output file in your
site.

There are different approaches.

In Code
~~~~~~~

For starters, you can simply call the bundle's ``urls()`` method:

.. code-block:: python

    >>> env['all_js'].urls()
    ('/media/gen/packed.js',)


Depending on the value of ``environment.debug``. it will either return
a list of all the bundle's source files, or the merged file pointed to
by the bundle's ``output`` option - all relative to the
``environment.url`` setting.

``urls()`` will always ensure that the files behind the urls it returns
actually exist. That is, it will merge and compress the source files in
production mode when first called, and update the compressed assets when
it detects changes. This behavior can be customized using various
:ref:`environment configuration values <environment-configuration>`.

Call ``urls()`` once per request, and pass the resulting list of urls to
your template, and you're good to go.


In templates
~~~~~~~~~~~~

For :doc:`some template languages </integration/index>`, webassets
includes extensions which allow you to access the bundles you defined.
Further, they usually allow you to define bundles on-the-fly, so you can
reference your assets directly from within your templates, rather than
predefining them in code.

For example, there is a template tag for :doc:`Jinja2 </integration/jinja2>`,
which allows you do something like this:

.. code-block:: jinja

    {% assets filters="cssmin,datauri", output="gen/packed.css", "common/jquery.css", "site/base.css", "site/widgets.css" %}
    ...


Management command
~~~~~~~~~~~~~~~~~~

In some cases you  might prefer to cause a manual build of your bundles
from the command line. See :doc:`/script` for more information.
