.. highlight:: python

------------
Installation
------------

Once ``django-assets`` is on your Python path (for example, use
``setup.py`` to install it), you need to register it with your Django
project.

Modify the ``INSTALLED_APPS`` setting to include the ``django_assets``
module::

    INSTALLED_APPS = (
        # ...,
        'django_assets',
    )

Now, the management command and the Django template tags and are
available to your project.

If you want to use ``django-assets`` with the Jinja 2 template language,
:doc:`additional steps are required <jinja2>`.

Running the tests
~~~~~~~~~~~~~~~~~

Nose is required to run the tests:

    http://somethingaboutorange.com/mrl/projects/nose/


---------
Upgrading
---------

When upgrading from an older version, you might encounter some backwards
incompatibility. The ``django-assets`` API is not stable yet.

From 0.1
~~~~~~~~

- The semantics of the ``ASSETS_DEBUG`` setting have changed. In 0.1,
  setting this to ``True`` meant *enable the django-assets debugging mode*.
  However, ``django-assets`` now follows the default Django ``DEBUG``
  setting, and ``ASSETS_DEBUG`` should be understood as meaning *how to
  behave when in debug mode*. See :ref:`ASSETS_DEBUG <settings-ASSETS_DEBUG>`
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