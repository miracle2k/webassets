=========
Upgrading
=========


When upgrading from an older version, you might encounter some backwards
incompatibility. The ``webassets`` API is not stable yet.


In Development version
~~~~~~~~~~~~~~~~~~~~~~

- Some filters now run in debug mode. Specifically, there are two things that
  deserve mention:

  - ``cssrewrite`` now runs when ``debug="merge"``. This is always what is
    wanted; it was essentially a bug that this didn't happen before.

  - All kinds of compiler-style filters (Sass, less, Coffeescript, JST
    templates etc). all now run in debug mode. The presence of such a filter
    causes bundles to be merged even while ``debug=True``.

    In practice, if you've been using custom custom bundle ``debug`` values
    to get such compilers to run, this will continue to work. Though it can
    now be simplified. Code like this::

        Bundle(
            Bundle('*.coffee', filters='coffeescript', debug=False)
            filters='jsmin')

    can be replaced with::

        Bundle('*.coffee', filters='coffeescript,jsmin')

    which has the same effect, which is that during debugging, Coffeescript
    will be compiled, but not minimized. This also allows you to define bundles
    that use compilers from within the templates tags, because nesting is no
    longer necessary.

    However, if you need to combine Coffeescript files (or other files needing
    compiling) with regular CSS or JS files, nesting is still required::

        Bundle('*.js'
               Bundle('*.coffee', filters='coffeescript'),
               filters='jsmin')

    If for some reason you do not want these compilers to run, you may still
    use a manual ``debug`` value to override the behavior. A case where this
    is useful is the ``less`` filter, which can be compiled in the browser::

        Bundle('*.less', filters='less', debug=True)

    Here, as long as the environment is in debug mode, the bundle will output
    the source urls, despite the ``less`` filter normally forcing a merge.

  As part of this new feature, the handling of nested bundle debug values
  has changed such that in rare cases you may see a different outcome. In
  the unlikely case that you are using these a lot, the rule is simple: The
  debug level can only ever be decreased. Child bundles cannot cannot do
  "more debugging" than their parent, and if  ``Environment.debug=False``,
  all bundle debug values are effectively ignored.

- The internal class names of filters have been renamed. For example,
  ``JSMinFilter`` is now simply ``JSMin``. This only affects you if you
  reference these classes directly, rather than using their id (such as
  ``jsmin``), which should be rare.


In 0.7
~~~~~~

There are some significant backwards incompatible changes in this release.

- The ``Environment.updater`` property (corresponds to the 
  ``ASSETS_UPDATER`` setting) can no longer be set to ``False`` or
  ``"never"`` in order to disable the automatic rebuilding. Instead, this
  now needs to be done using ``Environment.auto_build``, or the corresponding
  ``ASSETS_AUTO_BUILD`` setting.

- The ``Environment.expire`` (``ASSETS_EXPIRE``) option as been renamed to
  ``Environment.url_expire`` (``ASSETS_URL_EXPIRE``), and the default value
  is now ``True``.

- To disable automatic building, set the new ``Environment.auto_build``
  (``ASSETS_AUTO_BUILD``) option to ``False``. Before, this was done via
  the ``Environment.updater``, which is now deprecated.


Other changes:

- If ``Environment.auto_build`` is disabled, the API of Bundle.build()
  now assumes a default value of ``True`` for the ``force`` argument.
  This should not cause any problems, since it is the only call signature
  that really makes sense in this case.

- The former ``less`` filter, based on the old Ruby version of lessCSS
  (still available as the 1.x Ruby gems, but no longer developed) has been
  renamed ``less_ruby``, and ``less`` now uses the new NodeJS/Javascript
  implementation, which a while ago superseded the Ruby one.

- The ``rebuild`` command (of the command line mode) has been renamed to
  ``build``.

- The command line interface now requires the external dependency
  ``argparse`` on Python versions 2.6 and before. ``argparse`` is included
  with Python starting with version 2.7.

- ``PythonLoader.load_bundles()`` now returns a dict with the bundle names
  as keys, rather than a list.

- Filters now receive new keyword arguments. The API now officially requires
  filters to accept arbitrary ``**kwargs`` for compatibility with future
  versions. While the documentation has always suggested ``**kwargs`` be used,
  not all builtin filters followed this rule. Your custom filters may need
  updating as well.

- Filter classes now longer get an auto-generated name. If you have a custom
  filter and have not explicitly given it a name, you need to do this now if
  you want to register the filter globally.

- ``django_assets`` no longer tries to load a global ``assets.py`` module (it
  will still find bundles defined in application-level ``assets.py`` files). If
  you want to define bundles in other modules, you now need to list those
  explicitly in the :ref:`ASSETS_MODULES <django-setting-modules>` setting.

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
  argument. This was always intended for internal use and its existence
  not advertised, so its removal shouldn't cause too many problems.

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
