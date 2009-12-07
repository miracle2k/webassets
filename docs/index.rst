===========================================
django-assets - Asset management for Django
===========================================


Overview
========

Assets are defined inline in templates, except rather than referring to them
in a static manner, as you probably did so far, you are using the template
tag provided by this application:

.. code-block:: django

    {% load assets %}
    {% assets filter="jsmin", output="packed.js", "common/file1.js", "common/file2.js", "cadmin/file3.js" %}
        <script type="text/javascript" src="{{ ASSET_URL }}"></script>
    {% endassets %}

Apart from any number of source files, the following keyword-like
arguments can be passed to the template tag:

* ``output``:
    Name/path of the output file. All source files will be merged and the
    result stored at this location. This argument is required.
* ``filter``:
    One or multiple filters to apply. This argument is optional - if no
    filters are specified, the source files will merely be merged into the
    output file. Separate multiple filters by commas.

Note that all currently all filenames and paths are considered to be
relative to Django's ``MEDIA_ROOT`` setting.

The template will usually render it's contents once, for the given
``output`` file, though in debugging mode (see the ``ASSETS_URL`` setting),
it can render multiple times and generate references to the original source
files. All urls are prefixed with ``MEDIA_URL``.


How assets are built
--------------------

Assets can be regenerated automatically, or built manually using a
management command.

By default, if the filesystem modification date of any of the source files
exceeds the target file's modification date, the target will be recreated.
This behaviour can be disabled or changed using the ``ASSETS_UPDATER``
setting.

The management command for a manual rebuild is used like this::

	./manage.py assets rebuild

This will go through all the templates in your project and tries to find the
assets you have in use. It will then either create or recreate them.


More Information
================

.. toctree::
   :maxdepth: 1

   installation
   builtin_filters
   custom_filters
   settings
   jinja2
   faq

* :ref:`search`