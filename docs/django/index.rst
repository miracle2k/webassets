================================================
``django-assets`` - webassets Django integration
================================================


Quick Start
-----------

First, add ``django_assets`` to your ``INSTALLED_APPS`` setting:

.. code-block:: python

    INSTALLED_APPS = (
        ...,
        'django_assets',
    )

Create an ``assets.py`` file inside your application directory. This
is where you define your assets, and like Django's ``admin.py`` files,
they will automatically be picked up:

.. code-block:: python

    from django_assets import Bundle, register
    js = Bundle('common/jquery.js', 'site/base.js', 'site/widgets.js',
                filters='jsmin', output='gen/packed.js')
    register('js_all', js)


Then, include the bundle you defined in the appropriate place within your
templates:

.. code-block:: django

    {% load assets %}
    {% assets "js_all" %}
        <script type="text/javascript" src="{{ ASSET_URL }}"></script>
    {% endassets %}


That's it, really. ``django-assets`` will automatically merge and compress
your bundle's source files the first time the template is rendered, and will
automatically update the compressed file everytime a source file changes.
If :doc:`ASSETS_DEBUG <settings>` is enabled, then each source file
will be outputted individually instead.


Templates only
~~~~~~~~~~~~~~

If you prefer, you can also do without defining your bundles in code, and
simply define everything inside your template:

.. code-block:: django

    {% load assets %}
    {% assets filters="jsmin", output="gen/packed.js", "common/jquery.js", "site/base.js", "site/widgets.js" %}
        <script type="text/javascript" src="{{ ASSET_URL }}"></script>
    {% endassets %}


The management command
~~~~~~~~~~~~~~~~~~~~~~

``django-assets`` also provides a management command, ``manage.py assets``.
It can be used to manually cause your bundles to be rebuilt::

    $ ./manage.py assets rebuild
    Building asset: cache/site.js
    Building asset: cache/ie7.js
    Building asset: cache/site.css

Note that this is more difficult if you are defining your bundles within
your templates, rather than in code. You then need to use the
``--parse-templates`` option, so the rebuild command can find the bundles.

More about the management commands which are available (in generic,
non-Django specific form) can be found on the :doc:`../script` page.


Staticfiles support
~~~~~~~~~~~~~~~~~~~

When using ``django.contrib.staticfiles``, your CSS/Javascript source files
are spread across multiple directories.

``django-assets`` tries to "just work" here. When ``DEBUG=True``, and
``django.contrib.staticfiles`` is in ``INSTALLED_APPS``, it will
automatically use the staticfiles finder system to look for source files.

Thus, you can reference your media files in a bundle just as you would
otherwise. Output files are written to ``STATIC_ROOT``, which is however
not served by Django during development. If you are having bundles
built while in development mode, you will need to add
``django_assets.finders.AssetsFinder`` to your ``STATICFILES_FINDERS``
setting to have Django serve them.

In production mode, ``django-assets`` will expect all source files
to be located within ``STATIC_ROOT``. It will not use the ``staticfiles``
finder system to locate source files. You are expected to call the
``./manage.py collectstatic`` command before running
``./manage.py assets rebuild``. If you are using automatic rebuilding,
changes will currently not be picked up in production until you have run
``collectstatic``.


``CachedStaticFileStorage``
+++++++++++++++++++++++++++

The new ``CachedStaticFileStorage`` in Django 1.4 is able to rename all files
to include their content hash in the filename, and rewrite references within
your code. This is somewhat overlapping with our own
:doc:`versioning system </expiry>`.

If you prefer to use ``CachedStaticFileStorage``, you shouldn't run into any
problems. Just make sure you run ``./manage.py assets build`` first, and
``./manage.py collectstatic`` second.

This only doesn't *just work* if you are defining bundles in your templates.
If that is the case, you currently need to define a ``ASSETS_ROOT`` setting
that points to a different directory then ``STATIC_ROOT``. Only then will
``collectstatic`` be able to find the output files created with
``./manage.py build --parse-templates``, and process them into
``STATIC_ROOT``, like any other static file.


Jinja2 support
~~~~~~~~~~~~~~

See :doc:`jinja2` if you want to use ``django-assets`` with the Jinja2
templating language.


Further Reading
---------------

.. toctree::
    :maxdepth: 1

    settings
    All about bundles <../bundles>
    ../builtin_filters
    ../custom_filters
    ../css_compilers
    jinja2
    ../faq
