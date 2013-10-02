.. _index:

=======================================
webassets - Asset management for Python
=======================================

------------
Introduction
------------

webassets is a general, dependency-indepenant library for manage assets
the assets of your web application. It can merge and compress your CSS
and JavaScript files, supporting a wide variety of different filters,
and supports you working with compilers like CoffeeScript or Sass.


---------------------
Framework integration
---------------------

For some web frameworks, ``webassets`` provides special
integration. If you are using one of the supported frameworks, to go
the respective page:

.. toctree::
   :maxdepth: 1

   With Django <http://elsdoerfer.name/docs/django-assets/>
   With Flask <http://elsdoerfer.name/docs/flask-assets/>
   With Pyramid <https://github.com/sontek/pyramid_webassets>
   Other or no framework <generic/index>


----------------------
Detailed documentation
----------------------

This documentation also includes some pages with are applicable regardless
of framework used:

.. toctree::
   :maxdepth: 2

   environment
   bundles
   script
   builtin_filters
   expiring
   custom_filters
   css_compilers
   loaders
   integration/index
   faq
   upgrading
