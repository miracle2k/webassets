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


Is Google App Engine supported?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It generally works, though further improvements are planned. Due to the
way Google App Engine works (static files are stored on separate servers),
you need to build your assets locally, possibly using one of the management
commands provided for your preferred framework, and then deploy them.

In production mode, you therefore want to disable the
``Environment.updater``/``ASSETS_UPDATER`` setting.

Further, you currently need to disable
``Environment.expire``/``ASSETS_EXPIRE`` for webassets to work on Google's
servers. This means you will not get url expiration functionality. This will
be fixed in the future. In the meantime, you can write some custom code
to provide the feature. See `this gist <https://gist.github.com/1307521>`_
for an example.

There is a barebone Google App Engine example in the
`examples/appengine/ <https://github.com/miracle2k/webassets/blob/master/tests/>`_
folder.
