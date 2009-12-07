===========================================
django-assets - Asset management for Django
===========================================


In a nutshell
=============

Step 1: Define your assets
--------------------------

Assets can be defined inline in templates:

.. code-block:: django

    {% load assets %}
    {% assets filter="jsmin", output="gen/packed.js", "common/jquery.js", "site/base.js", "site/widgets.js" %}
        <script type="text/javascript" src="{{ ASSET_URL }}"></script>
    {% endassets %}

Or in your application code:

.. code-block:: python

	from django_assets import Bundle, register
	js = Bundle('common/jquery.js', 'site/base.js', 'site/widgets.js',
	            filters='jsmin', output='gen/packed.js')
	register('js_all', js)

.. code-block:: django

    {% assets "js_all" %}<script type="text/javascript" src="{{ ASSET_URL }}"></script>{% endassets %}

For more information, see :doc:`defining your assets <bundles>`.

Step 2: Build your assets
-------------------------

Your assets are regenerated automatically whenever the source files
change. Your done!

If that's not enough, you can use the managenment command to force a
rebuild::

	$ ./manage.py assets rebuild

For more information, see :doc:`building your assets <building>`.

In Detail
=========

.. toctree::
   :maxdepth: 1

   installation
   bundles
   building
   builtin_filters
   custom_filters
   settings
   jinja2
   faq

* :ref:`search`