========
Werkzeug
========

If you are using `Werkzeug`_, you may want to integrate the
**webassets** :doc:`CLI interface </script>` with your management
script built using `werkzeug.script`_.

.. _Werkzeug: http://werkzeug.pocoo.org/
.. _werkzeug.script: http://werkzeug.pocoo.org/documentation/0.6.2/script.html

This is how:

.. code-block:: python

    from webassets.ext.werkzeug import make_assets_action
    action_assets = make_assets_action(assets_env)

    from werkzeug import script
    script.run()


If you need to, you can specify a list of additional loaders which will
be used to complete the list of bundles. You usually want to do this if
you define your bundles inline in your templates, and thus need the
management command to parse your templates to find those bundles:

.. code-block:: python

    from webassets.ext.jinja2 import Jinja2Loader
    from webassets.ext.werkzeug import make_assets_action

    loader = Jinja2Loader(assets_env, [TEMPLATE_DIRECTORY], [jinja2_env])
    action_assets = make_assets_action(assets_env, [loader])

    from werkzeug import script
    script.run()


Because `werkzeug.script`` does not support subcommands, all the commands
are implemented as options, of which you must choose one::

    $ ./manage.py assets --rebuild
    $ ./manage.py assets --watch
    $ ./manage.py assets --clean
