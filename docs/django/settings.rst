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

.. autodata:: ASSETS_UPDATER
    :noindex:

.. _django-setting-expire:

.. autodata:: ASSETS_EXPIRE
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
