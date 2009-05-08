.. TODO: Merge this with the docstrings inside the settings module, and use
   autodoc to generate.

Settings
--------

The following setings are available.

ASSETS_DEBUG
~~~~~~~~~~~~

Can be used to switch off or modify asset functionality during debugging. 
Apart from ``False``, the supported values are ``nomerge`` and ``nofilter``,
the latter only disabling the application of filters, the former causing the
unmodified source files to be given out.

It is common to make this value dependent on your ``DEBUG`` setting.


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


ASSETS_AUTO_CREATE 
~~~~~~~~~~~~~~~~~~

Defaults to ``True`` and can be used to disable automatic creation of an 
asset even if it does not yet even exist. This is useful in combination with 
``ASSETS_UPDATER='never'``, to disable any sort of automatic asset building.


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
