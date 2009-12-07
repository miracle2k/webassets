---------------
Building assets
---------------

You have properly :doc:`defined your assets <bundles>`, now it's time for
``django-assets`` to work it's magic. You're deploying, and want your
media files merged and compressed.

There are two different ways to do so.


Automatically
-------------

By default, whenever a change in one of the source files is detected,
the bundle it belongs to will be regenerated. Changes are detected
by looking at the ``lastmod`` timestamp of both the source files and
the target files.

You can change this behavior by using the :ref:`settings-ASSETS_UPDATER`
setting. Currently, only the timestamp-based updater is available.

Setting the option to ``False`` will disable the automatic building of
assets.  In addition, you might want to disable
:ref:`settings-ASSETS_AUTO_CREATE`; otherwise, your bundles will still
be automatically built the first time, when they didn't exist before,
regardless of the active updater.


Manually
--------

Alternatively, there is a management command that will allow you to
force a rebuild of your assets whenever you like to::

	$ ./manage.py assets rebuild
	Building asset: cache/site.js
	Building asset: cache/ie7.js
	Building asset: cache/site.css

This works well if you have defined your bundles in code and registered
with the system. If your assets are defined directly inside your templates,
things are not quite as simple, since ``django-assets`` cannot easily
tell which those are.

To build assets defined in templates, you need to pass the
``--parse-temlates`` option:

if they are inside teplates, do::

	$ ./manage.py assets rebuild --parse-templates
	Searching templates...
	Parsed 156 templates, found 3 valid assets.
	Building asset: cache/site.js
	Building asset: cache/ie7.js
	Building asset: cache/site.css

When :doc:`using Jinja2 <jinja2>`, particular attention needs to be
payed to ensuring that ``django-assets`` is able to load your templates.
