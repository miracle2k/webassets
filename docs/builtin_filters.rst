.. module:: webassets.filter

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

.. autoclass:: webassets.filter.rjsmin.RJSMin


``yui_js``
~~~~~~~~~~

.. automodule:: webassets.filter.yui
.. autoclass:: webassets.filter.yui.YUIJS


``closure_js``
~~~~~~~~~~~~~~

.. automodule:: webassets.filter.closure


``uglifyjs``
~~~~~~~~~~~~

.. autoclass:: webassets.filter.uglifyjs.UglifyJS


``jsmin``
~~~~~~~~~

.. autoclass:: webassets.filter.jsmin.JSMin


``jspacker``
~~~~~~~~~~~~

.. autoclass:: webassets.filter.jspacker.JSPacker


CSS compressors
---------------

``cssmin``
~~~~~~~~~~

.. autoclass:: webassets.filter.cssmin.CSSMin


``cssutils``
~~~~~~~~~~~~

.. autoclass:: webassets.filter.cssutils.CSSUtils


``yui_css``
~~~~~~~~~~~

.. autoclass:: webassets.filter.yui.YUICSS


``cleancss``
~~~~~~~~~~~~

.. autoclass:: webassets.filter.cleancss.CleanCSS


``slimmer_css``
~~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.slimmer.CSSSlimmer


.. _filters-css-compilers:

JS/CSS compilers
----------------

``clevercss``
~~~~~~~~~~~~~

.. autoclass:: webassets.filter.clevercss.CleverCSS


.. _filters-less:

``less``
~~~~~~~~

.. autoclass:: webassets.filter.less.Less


``less_ruby``
~~~~~~~~~~~~~

.. autoclass:: webassets.filter.less_ruby.Less


.. _filters-sass:

``sass``
~~~~~~~~

.. autoclass:: webassets.filter.sass.Sass


``scss``
~~~~~~~~

.. autoclass:: webassets.filter.sass.SCSS


``compass``
~~~~~~~~~~~

.. autoclass:: webassets.filter.compass.Compass


``pyscss``
~~~~~~~~~~

.. autoclass:: webassets.filter.pyscss.PyScss


``stylus``
~~~~~~~~~~

.. autoclass:: webassets.filter.stylus.Stylus


``coffeescript``
~~~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.coffeescript.CoffeeScript


JavaScript templates
--------------------

``jst``
~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.jst.JST


``handlebars``
~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.handlebars.Handlebars


``dustjs``
~~~~~~~~~~

.. autoclass:: webassets.filter.dust.DustJS


Other
-----

.. _filters-cssrewrite:

``cssrewrite``
~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.cssrewrite.CSSRewrite


``datauri``
~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.datauri.CSSDataUri


``cssprefixer``
~~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.cssprefixer.CSSPrefixer


``gzip``
~~~~~~~~

.. autoclass:: webassets.filter.gzip.GZip


``jinja2``
~~~~~~~~~~

.. autoclass:: webassets.filter.jinja2.Jinja2


``spritemapper``
~~~~~~~~~~~~~~~~

.. autoclass:: webassets.filter.spritemapper.Spritemapper
