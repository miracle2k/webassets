======================
Command Line Interface
======================

.. TODO: Link to the Integration page, and a page explaining how to use the interface in generic mode


--------
Commands
--------

rebuild
-------

Rebuilds all bundles, regardless of whether they are detected as having
changed or not.


watch
-----

Start a daemon which monitors your bundle source files, and
automatically rebuilds bundles when a change is detected:

This can be useful during development, if building is not instantaneous,
and you are loosing valuable time waiting for the build to finish while
trying to access your site.


clean
-----

Will clear out the cache, which after a while can grow quite large.