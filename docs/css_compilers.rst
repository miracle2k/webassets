.. _css-compilers:

CSS compilers
=============

CSS compilers intend to improve upon the default CSS syntax, allow you
to write your stylesheets in a syntax more powerful, or more easily
readable. Since browsers do understand this new syntax, the CSS compiler
needs to translate it's own syntax to original CSS.

``webassets`` includes :ref:`builtin filters for a number of popular
CSS compilers <filters-css-compilers>`, which you can use like any other
filter. There is one problem though: While developing, you will probably
want to disable asset packaging, and instead work with the uncompressed
assets (i.e., you would disable the
:ref:`environment.debug <environment-setting-debug>` option). However,
you still need to apply the filter for your CSS compiler, since otherwise,
the Browser wouldn't understand your stylesheets.

Enabling debugging mode would disable the CSS compilation; Disabling
debugging would apply the compression. Using a simple ``if-else`` when
defining your bundles will not suffice for all cases. Once you need to
merge raw CSS files and compiled CSS files together, you need to start
using nested bundles:

.. code-block:: python

    less = Bundle('css/base.less', 'css/forms.less',
                  filters='less', output='gen/less.css',
                  debug=False)
    env.register('all-css',
                 less, 'css/jquery.calendar.css',
                 filters='yui_css', output="gen/all.css")

The magic here is in the ``debug`` argument passed the the ``less``
bundle. Setting it to ``False`` means that even when the rest of the system
is in debug mode, and no filters will be applied, this bundle is not:
the less files will still be compiled.
