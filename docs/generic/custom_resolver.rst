.. _django_assets: https://github.com/miracle2k/django-assets


.. py:currentmodule:: webassets.env

Custom resolvers
================

The resolver is a pluggable object that webassets uses to find the
contents of a :class:`Bundle` on the filesystem, as well as to
generate the correct urls to these files.

For example, the default resolver searches the
:attr:`Environment.load_path`, or looks within
:attr:`Environment.directory`. The `webassets Django integration`__
will use Django's *staticfile finders* to look for files.

__ django_assets_

For normal usage, you will not need to write your own resolver, or
indeed need to know how they work. However, if you want to integrate
``webassets`` with another framework, or if your application is
complex enough that it requires custom file referencing, read on.


The API as webassets sees it
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``webassets`` expects to find the resolver via the
:attr:`Environment.resolver` property, and expects this object to
provide the following methods:

.. automethod:: Resolver.resolve_source

.. automethod:: Resolver.resolve_output_to_path

.. automethod:: Resolver.resolve_source_to_url

.. automethod:: Resolver.resolve_output_to_url


Methods to overwrite
~~~~~~~~~~~~~~~~~~~~

However, in practice, you will usually want to override the builtin
:class:`Resolver`, and customize it's behaviour where necessary. The
default resolver already splits what is is doing into multiple
methods; so that you can either override them, or
refer to them in your own implementation, as makes sense.

Instead of the official entrypoints above, you may instead prefer
to override the following methods of the default resolver class:

.. automethod:: Resolver.search_for_source

.. automethod:: Resolver.search_load_path


Helpers to use
~~~~~~~~~~~~~~

The following methods of the default resolver class you may find
useful as helpers while implementing your subclass:

.. automethod:: Resolver.consider_single_directory

.. automethod:: Resolver.glob

.. automethod:: Resolver.query_url_mapping



Example: A prefix resolver
--------------------------

The following is a simple resolver implementation that searches
for files in a different directory depending on the first
directory part.

.. code-block:: python

    from webassets.env import Resolver

    class PrefixResolver(Resolver):

        def __init__(self, prefixmap):
            self.map = prefixmap

        def search_for_source(self, ctx, item):
            parts = item.split('/', 1)
            if len(parts) < 2:
                raise ValueError(
                    '"%s" not valid; a static path requires a prefix.' % item)

            prefix, name = parts
            if not prefix in self.map:
                raise ValueError(('Prefix "%s" of static path "%s" is not '
                                  'registered') % (prefix, item))

            # For the rest, defer to base class method, which provides
            # support for things like globbing.
            return self.consider_single_directory(self.map[prefix], name)


Using it:

.. code-block:: python

     env = webassets.Environment(path, url)
     env.resolver = PrefixResolver({
         'app1': '/var/www/app1/static',
         'app2': '/srv/deploy/media/app2',
     })
     bundle = Bundle(
        'app2/scripts/jquery.js',
        'app1/*.js',
     )


Other implementations
---------------------

- `django-assets Resolver <https://github.com/miracle2k/django-assets/blob/master/django_assets/env.py>`_
  (search for ``class DjangoResolver``).
- `Flask-Assets Resolver <https://github.com/miracle2k/flask-assets/blob/master/src/flask_assets.py>`_
  (search for ``class FlaskResolver``).
- `pyramid_webassets Resolver <https://github.com/sontek/pyramid_webassets/blob/master/pyramid_webassets/__init__.py>`_
  (search for ``class PyramidResolver``).
