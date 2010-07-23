=========
Upgrading
=========


When upgrading from an older version, you might encounter some backwards
incompatibility. The ``webassets`` API is not stable yet.


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
  optinally an ``is_source_filter`` attribute, those now have been replaced
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