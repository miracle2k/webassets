.. TODO: Merge this with the docstrings inside the settings module, and use
   autodoc to generate.

Settings
--------

The following settings are available.

.. _settings-ASSETS_DEBUG:

ASSETS_DEBUG
~~~~~~~~~~~~

.. TODO: We could link bundle in this paragraph.

Configures how `django-assets`` is supposed to behave when Django is in
debug mode (``DEBUG`` being enabled). Specifically, this is the default
value for the ``debug`` option of a Bundle.

Note that this does **not** enable debugging itself.

There are three possible values:

- ``True`` - debug ``django-assets`` as well, that is, output all the
  source files, instead of merging bundles together and applying filters.
  **This is the default.**
- ``False`` - do not debug ``django-assets``. Behave exactly as in
  production mode, merging bundles and applying filters.
- ``"merge"`` - Do merge files source files together, but do not apply
  filters. This is a popular alternative to full debugging, since it comes
  with some performance gains through fewer requests, while still giving
  you access to the raw source code.


.. _settings-ASSETS_UPDATER:

ASSETS_UPDATER
~~~~~~~~~~~~~~

Modifies the auto-rebuild behaviour. By default, this is set to
``timestamp``, i.e. assets will be updated when a change can be determined
via the filesystem modification dates.

Currently, the only other usable values are ``'always'`` and ``'never'``,
the  former only recommended during debugging, the latter useful if you want
to limit yourself to manual building.

Note that when using ``never``, your assets will initially still be created
automatically when they do not exist yet. See ``ASSETS_AUTO_CREATE``.


.. _settings-ASSETS_AUTO_CREATE:

ASSETS_AUTO_CREATE
~~~~~~~~~~~~~~~~~~

Defaults to ``True`` and can be used to disable automatic creation of an
asset even if it does not yet even exist. This is useful in combination
with ``ASSETS_UPDATER='never'``, to disable any sort of automatic asset
building.

.. _settings-ASSETS_EXPIRE:

ASSETS_EXPIRE
~~~~~~~~~~~~~

Is needed if you send your assets to the client using a far future expires
header. Unless set to ``False``, it will modify the asset url using it's
modification timestamp, so that browsers will reload the file when necessary.
Possible values are ``'querystring'`` (*asset.js?1212592199*) and
``'filename'`` (*asset.1212592199.js*). The latter might work better with
certain proxies or exotic browers, but will require you to rewrite those
modified filenames via your webserver.


ASSETS_JINJA2_EXTENSIONS
~~~~~~~~~~~~~~~~~~~~~~~~~

Is needed in some cases if you want to use ``django-assets`` with the
Jinja 2 template system. For more information, see :doc:`jinja2`.
