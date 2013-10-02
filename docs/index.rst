.. _index:

=======================================
webassets - Asset management for Python
=======================================

------------
Introduction
------------

Webassets is a library that allows you to manage assets for your web
applications. Css and javascript files that are sent to the client are
examples of assets. These files have to be specially managed.

1. They have to be minified and bundled to reduce the amount of
   traffic necessary to obtain all of them.
2. They have to be refetched when there's a change in any of them.

While it's possible to do these things manually, the ``webassets``
library takes care of the headache for you. 


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
