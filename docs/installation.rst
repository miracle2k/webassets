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

- The YUI Javascript filter can no longer be referenced via ``yui``.
  Instead, you need to explicitly specify which filter you want to use,
  ``yui_js`` or ``yui_css``.