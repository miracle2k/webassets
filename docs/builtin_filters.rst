.. _builtin-filters:

================
Included Filters
================

The following filters are included in ``webassets``, though some may
require the installation of an external library, or the availability of
external tools.

You can also write :doc:`custom filters <custom_filters>`.


Javascript compressors
----------------------

``rjsmin``
~~~~~~~~~~

.. autoclass:: webassets.filter.rjsmin.RJSMinFilter


``yui_js``
~~~~~~~~~~

.. automodule:: webassets.filter.yui
.. autoclass:: webassets.filter.yui.YUIJSFilter


``closure_js``
~~~~~~~~~~~~~~

.. automodule:: webassets.filter.closure


``uglifyjs``
~~~~~~~~~~~~

.. automodule:: webassets.filter.uglifyjs


``jsmin``
~~~~~~~~~

.. autoclass:: webassets.filter.jsmin.JSMinFilter


``jspacker``
~~~~~~~~~~~~

.. autoclass:: webassets.filter.jspacker.JSPackerFilter


CSS compressors
---------------

``cssmin``
~~~~~~~~~~

.. autoclass:: webassets.filter.cssmin.CSSMinFilter


``cssutils``
~~~~~~~~~~~~

.. autoclass:: webassets.filter.cssutils.CSSUtilsFilter


``yui_css``
~~~~~~~~~~~

.. autoclass:: webassets.filter.yui.YUICSSFilter


.. _filters-css-compilers:

CSS Compilers
-------------

``clevercss``
~~~~~~~~~~~~~

.. autoclass:: webassets.filter.clevercss.CleverCSSFilter


.. _filters-less:

``less``
~~~~~~~~

.. autoclass:: webassets.filter.less.LessFilter


.. _filters-sass:

``sass``
~~~~~~~~

.. autoclass:: webassets.filter.sass.SassFilter


``scss``
~~~~~~~~

.. autoclass:: webassets.filter.sass.SCSSFilter


``compass``
~~~~~~~~~~~

.. autoclass:: webassets.filter.compass.CompassFilter


Other
-----

.. _filters-cssrewrite:

``cssrewrite``
~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.cssrewrite.CSSRewriteFilter


``jst``
~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.jst.JSTFilter


``cssprefixer``
~~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.cssprefixer.CSSPrefixerFilter


``gzip``
~~~~~~~~

.. autoclass:: webassets.filter.gzip.GZipFilter


``coffeescript``
~~~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.coffeescript.CoffeeScriptFilter
