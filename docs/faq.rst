.. _faq:

FAQ
---

Is there a cache-busting feature?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes! It's turned on by default. See the
:ref:`Environment.expire <environment-setting-expire>`
option (or :ref:`ASSETS_EXPIRE <django-setting-expire>` if using
``django_assets``).


Relative URLs in my CSS code break if the merged asset is written to a different location than the source files. How do I fix this?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the builtin :ref:`cssrewrite <filters-cssrewrite>` filter which
will transparently fix ``url()`` instructions in CSS files on the fly.


I am using a CSS compiler and I need it's filter to apply even in debug mode!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See :doc:`css_compilers` for how this is best done.