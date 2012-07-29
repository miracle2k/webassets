.. _environment:

===============
The environment
===============

.. currentmodule:: webassets.env

The environment has two responsibilities: One, it acts as a registry for
bundles, meaning you only have to pass around a single object to access
all your bundles.

Also, it holds the configuration.


Registering bundles
===================

Bundles can be registered with the environment:

.. code-block:: python

    my_bundle = Bundle(...)
    environment.register('my_bundle', my_bundle)


A shortcut syntax is also available - you may simply call ``register()``
with the arguments which you would pass to the ``Bundle`` constructor:

.. code-block:: python

    environment.register('my_bundle', 'file1.js', 'file2.js', output='packed.js')


The environment allows dictionary-style access to the registered bundles:

.. code-block:: python

    >>> len(environment)
    1

    >>> list(environment)
    [<Bundle ...>]

    >>> environment['my_bundle']
    <Bundle ...>


.. _environment-configuration:

Configuration
=============

The environment supports the following configuration options:

.. autoattribute:: webassets.env.Environment.directory

.. autoattribute:: webassets.env.Environment.url

.. _environment-setting-debug:

.. autoattribute:: webassets.env.Environment.debug

.. autoattribute:: webassets.env.Environment.auto_build

.. autoattribute:: webassets.env.Environment.url_expire

.. autoattribute:: webassets.env.Environment.versions

.. autoattribute:: webassets.env.Environment.manifest

.. autoattribute:: webassets.env.Environment.cache

.. autoattribute:: webassets.env.Environment.load_path

.. autoattribute:: webassets.env.Environment.url_mapping


Filter configuration
====================

In addition to the standard options listed above, you can set custom
configuration values using ``Environment.config``. This is so that you can
configure filters through the environment:

.. code-block:: python

    environment.config['sass_bin'] = '/opt/sass/bin/sass')

This allows the :ref:`Sass filter <filters-sass>` to find the sass
binary.

Note: Filters usually allow you to define these values as system
environment variables as well. That is, you could also define a
``SASS_BIN`` environment variable to setup the filter.
