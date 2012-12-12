.. _css-compilers:

CSS compilers
=============

CSS compilers intend to improve upon the default CSS syntax, allow you
to write your stylesheets in a syntax more powerful, or more easily
readable. Since browsers do not understand this new syntax, the CSS compiler
needs to translate its own syntax to original CSS.

``webassets`` includes :ref:`builtin filters for a number of popular
CSS compilers <filters-css-compilers>`, which you can use like any other
filter. There is one problem though: While developing, you will probably
want to disable asset packaging, and instead work with the uncompressed
assets (i.e., you would disable the
:ref:`environment.debug <environment-setting-debug>` option). However,
you still need to apply the filter for your CSS compiler, since otherwise,
the Browser wouldn't understand your stylesheets.

For this reason, such compiler filters run even when in debug mode:

.. code-block:: python

    less = Bundle('css/base.less', 'css/forms.less',
                  filters='less,cssmin', output='screen.css')

The above code block behaves exactly like you would want it to: When
debugging, the less files are compiled to CSS, but the code is not minified.
In production, both filters are applied.

Sometimes, you need to merge together good old CSS code, and you have a
compiler that, unlike ``less``, cannot process those. Then you can use a
child bundle:

.. code-block:: python

    sass = Bundle('*.sass' filters='sass', output='gen/sass.css')
    all_css = Bundle('css/jquery.calendar.css', sass,
                     filters='cssmin', output="gen/all.css")

In the above case, the ``sass`` filter is only applied to the Sass source
files, within a nested bundle (which needs it's own output target!). The
minification is applied to all CSS content in the outer bundle.
