Standalone example
==================

This shows how you might use ``webassets`` outside of a Python project.

A global script ``webassets`` is installed by the Pyton package. In this
directory, run::

     $ webasssets -c bundles.yaml build

.. note::
    You need to have the ``clevercss`` PyPI package installed.

Then open ``index.html`` in your browser. The page will use the compressed
stylesheet that you have just built.
