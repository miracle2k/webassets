.. _faq:

FAQ
---

Is there a cache-busting feature?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes! See :doc:`/expiring`.


Relative URLs in my CSS code break if the merged asset is written to a different location than the source files. How do I fix this?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the builtin :ref:`cssrewrite <filters-cssrewrite>` filter which
will transparently fix ``url()`` instructions in CSS files on the fly.


I am using a CSS compiler and I need its filter to apply even in debug mode!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See :doc:`css_compilers` for how this is best done.


Is Google App Engine supported?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes. Due to the way Google App Engine works (static files are stored on
separate servers), you need to build your assets locally, possibly using one
of the management commands provided for your preferred framework, and then
deploy them.

In production mode, you need to disable the ``Environment.auto_build`` setting.

For URL expiry functionality, you need to use a manifest that holds version
information. See :doc:`/expiring`.

There is a barebone Google App Engine example in the
`examples/appengine/ <https://github.com/miracle2k/webassets/blob/master/examples/appengine/>`_
folder.
