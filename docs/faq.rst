FAQ
---

Is there a cache-busting feature?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes! You simply need to turn on the :ref:`settings-ASSETS_EXPIRE`
setting (it is currently disabled by default).


Relative URLs in my CSS code break if the merged asset is written to a different location than the source files. How do I fix this?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the builtin :ref:`cssrewrite <filters-cssrewrite>` filter which
will transparently fix ``url()`` instructions in CSS files on the fly.


I am using a CSS compiler and I need it's filter to apply even in debug mode!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See the :ref:`section on CSS compilers <bundles-css_compilers>` for how
this is best done.