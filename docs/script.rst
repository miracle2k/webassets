======================
Command Line Interface
======================

While it's often convenient to have webassets automatically rebuild
your bundles on access, you sometimes may prefer to build manually,
for example for performance reasons in larger deployments.

*webassets* provides a command line interface which is supposed to help
you manage your bundles manually. However, due to the generic nature of
the webassets core library, it usually needs some help setting up.

You may want to check the :doc:`integration page </integration/index>`
to see if webassets already provides helpers to expose the command line
within your framework. If that is not the case, read on.


----------------------------------
Build a custom command line client
----------------------------------

In most cases, you can simply wrap around the ``webassets.script.main``
function. For example, the command provided by Flask-Assets looks like
this:

.. code-block:: python

    class ManageAssets(flaskext.script.Command):
        def __init__(self, assets_env):
            self.env = assets_env

        def handle(self, app, prog, name, remaining_args):
            from webassets import script
            script.main(remaining_args, env=self.env)


In cases where this isn't possible for some reason, or you need more
control, you can work directly with the
``webassets.script.CommandLineEnvironment`` class, which implements all
the commands as simple methods.

.. code-block:: python

    import logging
    from webassets.script import CommandLineEnvironment

    # Setup a logger
    log = logging.getLogger('webassets')
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.DEBUG)

    cmdenv = CommandLineEnvironment(assets_env, log)
    cmdenv.invoke('build')

    # This would also work
    cmdenv.build()


You are reponsible for parsing the command line in any way you see fit
(using for example the :py:mod:`optparse` or :py:mod:`argparse` libraries,
or whatever your framework provides as a command line utility shell), and
then invoking the corresponding methods on your instance of
``CommandLineEnvironment``.


.. _script-commands:

-----------------
Included Commands
-----------------

The following describes the commands that will be available to you through
the *webassets* CLI interface.

build
-------

Builds all bundles, regardless of whether they are detected as having changed
or not.


watch
-----

Start a daemon which monitors your bundle source files, and automatically
rebuilds bundles when a change is detected.

This can be useful during development, if building is not instantaneous, and
you are losing valuable time waiting for the build to finish while trying to
access your site.


clean
-----

Will clear out the cache, which after a while can grow quite large.
