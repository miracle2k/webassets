=========
Upgrading
=========


When upgrading from an older version, you might encounter some backwards
incompatibility. The ``webassets`` API is not stable yet.


In 0.10
~~~~~~~

- The :class:`Resolver` API has changed. Rather than being bound to an
  environment via the constructor, the individual methods now receive
  a ``ctx` object, which allows access to the environment's settings.

  See :ref:`the page on implementing resolvers <custom_resolver>`.

- The :meth:`Bundle.build` and :meth:`Bundle.url` methods no longer accept
  an environment argument. To work with a Bundle that is not attached to
  an environment already, use the following syntax instead::

      with bundle.bind(env):
          bundle.build()

- Filters can no longer access a ``self.env`` attribute. It has been renamed
  to ``self.ctx``, which provides a compatible object.


In 0.9
~~~~~~

- Python 2.5 is no longer supported.

- The API of the BaseCache.get() method has changed. It no longer receives
  a ``python`` keyword argument. This only affects you if you have
  implemented a custom cache class.


In 0.8
~~~~~~

- **django-assets is no longer included!**
  You need to install it's package separately. See the current
  `development version <https://github.com/miracle2k/django-assets>`_.

  .. warning::
    When upgrading, you need to take extra care to rid yourself of the old
    version of webassets before installing the separate ``django-assets``
    package. This is to avoid that Python still finds the old ``django_assets``
    module that used to be included with ``webassets``.

    In some cases, even ``pip uninstall webassets`` is not enough, and old
    ``*.pyc`` files are kept around. I recommend that you delete your old
    webassets install manually from the filesystem. To find out where it is
    stored, open a Python shell and do::

        >>> import webassets
        >>> webassets
        <module 'webassets' from '/usr/local/lib/python2.7/dist-packages/webassets/src/webassets/__init__.pyc'>

- Some filters now run in debug mode. Specifically, there are two things that
  deserve mention:

  - ``cssrewrite`` now runs when ``debug="merge"``. This is always what is
    wanted; it was essentially a bug that this didn't happen before.

  - All kinds of compiler-style filters (Sass, less, Coffeescript, JST
    templates etc). all now run in debug mode. The presence of such a filter
    causes bundles to be merged even while ``debug=True``.

    In practice, if you've been using custom bundle ``debug`` values to get
    such compilers to run, this will continue to work. Though it can now be
    simplified. Code like this::

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

- Removed the previously deprecated ``rebuild`` alias for the ``build`` command.

- Subtly changed how the ``auto_build`` setting affects the
  :meth:`Bundle.build` method: It doesn't anymore. Instead, the setting now
  only works on the level of :meth:`Bundle.urls`. The new behaviour is more
  consistent, makes more sense, and simplifies the code.

  The main backwards-incompatiblity caused by this is that when
  ``environment.auto_build=False``, and you are calling ``bundle.build()``
  without specifying an explicit ``force`` argument, it used to be the case
  that ``force=True`` was assumed, i.e. the bundle was built without looking
  at the timestamps to see if a rebuild is necessary. Now, the timestamps will
  be checked, unless ``force=True`` is explicitly given.

  In case you don't want to pass ``force=True``, you can instead also set
  the :attr:`Environment.updater` property to ``False``; without an updater
  to check timestamps, every ``build()`` call will act as if ``force=True``.

  **Note**: This only affects you if you work with the :meth:`Bundle.build`
  and :meth:`Bundle.url` methods directly. The behavior of the command line
  interface, or the template tags is not affected.

- The implementation of the :class:`CommandLineEnvironment` has changed, and
  each command is now a separate class. If you have been subclassing
  :class:`CommandLineEnvironment` to override individual command methods like
  :meth:`CommandLineEnvironment.build`, you need to update your code.

- The :class:`JavaMixin` helper class to implement Java-based filters has been
  removed, and in it's stead there is now a :class:`JavaTool` base class that
  can be used.

- The code to resolve bundle contents has been refactored. As a result, the
  behavior of the semi-internal method :meth:`Bundle.resolve_contents` has
  changed slightly; in addition, the
  :meth:`Environment._normalize_source_path` method used mainly by
  extensions like ``Flask-Assets`` has been removed. Instead, extensions now
  need to implement a custom :class:`Resolver`. The
  :class:`Evironment.absurl` method has also disappeared, and replacing it
  can now be done via a custom :class:`Resolver`` class.

- :attr:`Environment.directory` now always returns an absolute path; if a
  relative path is stored, it is based off on the current working directory.
  This spares *a lot* of calls to ``os.abspath`` throughout the code. If you
  need the original value you can always use
  ``environment.config['directory']``.

- If the ``JST_COMPILER`` option of the ``jst`` filter is set to ``False``
  (as opposed to the default value, ``None``), the templates will now be
  output as raw strings. Before, ``False`` behaved like ``None`` and used
  the builtin compiler.

- The API of the ``concat()`` filter method has changed. Instead of a
  list of hunks, it is now given a list of 2-tuples of
  ``(hunk, info_dict)``.

- The internal ``JSTTemplateFilter`` base class has changed API.
  - concat filter
  - jst handlebar filters have changed, use concat, base class has changed


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
  explicitly in the :ref:`ASSETS_MODULES <django:django-setting-modules>` setting.

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
  behave when in debug mode*. See :ref:`ASSETS_DEBUG <django:django-setting-debug>`
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
