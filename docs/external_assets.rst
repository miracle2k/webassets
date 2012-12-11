.. _external_assets:

===============
External Assets
===============

An external assets bundle is used to manage images, webfonts and other assets
that you wouldn't normally include in another bundle. Files will have a cache
buster applied (see :doc:`URL Expiry </expiring>`), and the
:ref:`cssrewrite <filters-cssrewrite>` filter can modify css files to point to
the versioned filenames.


Registering external files
--------------------------

An external assets bundle takes any number of input patterns and one output
directory.

.. code-block:: python

    ExternalAssets('images/*', 'more_images/*', output='versioned_images')

The output directory is relative to the ``directory`` setting of your
:doc:`environment <environment>`. All files found matching the input patterns
will be copied (with rewritten filenames) to this directory.


Using rewritten files
---------------------

CSS files using the :ref:`cssrewrite <filters-cssrewrite>` filter will be
automatically adapted to use the versioned filenames.

.. code-block:: python

    Bundle('style.css', filters=['cssrewrite'])


If you need to get the specific url for a file, you can request it from the
bundle directly using :meth:`ExternalAssets.url` directly.

.. code-block:: python

    >>> env['images'].url('logo.png')
    /static/logo.c49de0ce.png
