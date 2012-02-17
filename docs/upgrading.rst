=========
Upgrading
=========


When upgrading from an older version, you might encounter some backwards
incompatibility. The ``webassets`` API is not stable yet.


In Development version
~~~~~~~~~~~~~~~~~~~~~~

- If ``Environment.updater`` is disabled, the API of Bundle.build()
  now assumes a default value of ``True`` for the ``force`` argument.
  This should not case any problems, since it is the only call signature
  that really makes sense in this case.

- The former ``less`` filter, based on the old Ruby version of lessCSS
  (still available as the 1.x Ruby gems, but no longer developed) has been
  renamed ``less_ruby``, and ``less`` now uses the new NodeJS/Javascript
  implementation, which a while ago superseded the Ruby one.

- The ``rebuild`` command (of the command line mode) has ben renamed to
  ``build``.

- The command line interface now requires to external dependency
  ``argparse`` on Python versions 2.6 and before. ``argparse`` is included
  with Python starting with version 2.7.

- ``PythonLoader.load_bundles()`` now returns a dict with the bundle names
  as keys, rather than a list.


In 0.6
~~~~~~

- The ``Environment.updater`` class no longer support custom callables.
  Instead, you need to subclass ``BaseUpdater``. Nobody is likely to use
  this feature though.

- The cache is no longer debug-mode only. If you enable
  ``Environment.cache`` (``ASSETS_CACHE`` in ``django-assets``),
  the cache will be enabled regardless of the
  ``Environment.debug``/``ASSETS_DEBUG`` option. If you want the old
  behavior, you can easily configure it manually.

- The ``Bundle.build`` method no longer takes the ``no_filters``
  argument. This was always intended for internal use and it's existence
  not advertised, so it's removal shouldn't cause too many problems.

- The ``Bundle.build`` method now returns a list of ``FileHunk`` objects,
  rather than a single one. It now works for container bundles (bundles
  which only have other bundles for children, not files), rather than
  raising an exception.

- The ``rebuild`` command now ignores a ``debug=False`` setting, and
  forces a build in production mode instead.


In 0.4
~~~~~~

- Within ``django_assets``. the semantics of the ``debug`` setting have
  changed again. It once again allows you to specifically enable debug mode
  for the assets handling, irrespective of Django's own ``DEBUG`` setting.

- ``RegistryError`` is now ``RegisterError``.

- The ``ASSETS_AUTO_CREATE`` option no longer exists. Instead, automatic
  creation of bundle output files is now bound to the ``ASSETS_UPDATER``
  setting. If it is ``False``, i.e. automatic updating is disabled, then
  assets won't be automatically created either.

In 0.2
~~~~~~

- The filter API has changed. Rather than defining an ``apply`` method and
  optionally an ``is_source_filter`` attribute, those now have been replaced
  by ``input()`` and ``output()`` methods. As a result, a single filter can
  now act as both an input and an output filter.

In 0.1
~~~~~~

- The semantics of the ``ASSETS_DEBUG`` setting have changed. In 0.1,
  setting this to ``True`` meant *enable the django-assets debugging mode*.
  However, ``django-assets`` now follows the default Django ``DEBUG``
  setting, and ``ASSETS_DEBUG`` should be understood as meaning *how to
  behave when in debug mode*. See :ref:`ASSETS_DEBUG <django-setting-debug>`
  for more information.
- ``ASSETS_AUTO_CREATE`` now causes an error to be thrown if due it it
  being disabled a file cannot be created. Previously, it caused
  the source files to be linked directly (as if debug mode were active).

  This was done due to ``Explicit is better than implicit``, and for
  security considerations; people might trusting their comments to be
  removed. If it turns out to be necessary, the functionality to fall
  back to source could be added again in a future version through a
  separate setting.
- The YUI Javascript filter can no longer be referenced via ``yui``.
  Instead, you need to explicitly specify which filter you want to use,
  ``yui_js`` or ``yui_css``.
