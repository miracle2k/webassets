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