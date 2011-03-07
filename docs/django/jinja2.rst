Jinja2 support
--------------

``django-assets`` strives to offer full support for the `Jinja2 template
language <http://jinja.pocoo.org/2/>`_.

A Jinja2 extension is available as ``webassets.ext.jinja2.AssetsExtension``.
It will provide a ``{% assets %}`` tag that functions pretty much like the
Django template version, except inheriting the more expressive syntax of
Jinja. For example, filters may be specified as tuples:

.. code-block:: django

    {% assets filters=("jsmin", "gzip") ... %}


More exhaustive documentation of the Jinja2 tag can be
:doc:`here </integration/jinja2>`.


Installation
~~~~~~~~~~~~

How you enable the Jinja2 extension depends on how you are integrating
Jinja with Django. For example:

* If you are using `Coffin <https://launchpad.net/coffin>`_, you don't have
  to do anything at all: The extension will be available at the moment
  ``django-assets`` is added to ``INSTALLED_APPS``.

* If you are creating your Jinja2 environment manually, you can
  simply use it's ``extensions`` parameter and specify
  ``webassets.ext.jinja2.AssetsExtension``.

However, there is a minor difficulty if you intend to use the management
command to manually rebuild assets: Since that step involves parsing your
templates, the command needs to know what other Jinja2 extensions you are
using to successfully do so. Because there is no "one way" to integrate
Jinja and Django, it can't determine the extensions you are using all by
itself. Instead, it expects you to specify the ``ASSETS_JINJA2_EXTENSIONS``
setting. In most cases, you would simply to something like::

    ASSETS_JINJA2_EXTENSIONS = JINJA2_EXTENSIONS

i.e. aliasing it to the actual setting you are using.

Again, if you are using Coffin, you may disgard this step as well, since
your Coffin environment will automatically be used.