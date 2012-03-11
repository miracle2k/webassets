========
Settings
========

.. currentmodule:: django_assets.settings

There are a bunch of values which you can define in your Django ``settings``
module to modify the behaviour of ``webassets``.

Note: This document places those values inside the ``django_assets.settings``
module. This is irrelevant. To change the values, you need to define them
in your project's global settings.


.. autodata:: ASSETS_ROOT
    :noindex:

.. autodata:: ASSETS_URL
    :noindex:

.. _django-setting-debug:

.. autodata:: ASSETS_DEBUG
    :noindex:

.. autodata:: ASSETS_AUTO_BUILD
    :noindex:

.. autodata:: ASSETS_URL_EXPIRE
    :noindex:

.. autodata:: ASSETS_VERSIONS
    :noindex:

.. autodata:: ASSETS_MANIFEST
    :noindex:

.. autodata:: ASSETS_CACHE
    :noindex:

.. data:: ASSETS_JINJA2_EXTENSIONS
    :noindex:

    This is needed in some cases when you want to use ``django-assets`` with
    the Jinja 2 template system. It should be a list of extensions you are
    using with Jinja 2, using which it should be possible to construct a
    Jinja 2 environment which can parse your templates. For more information,
    see :doc:`jinja2`.

.. _django-setting-modules:

.. data:: ASSETS_MODULES
    :noindex:

    ``django-assets`` will automatically look for ``assets.py`` files in each
    application, where you can register your bundles. If you want additional
    modules to be loaded, you can define this setting. It expects a list of
    importable modules::

        ASSETS_MODULES = [
            'myproject.assets'
        ]
