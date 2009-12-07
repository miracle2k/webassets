-----------------------
Creating custom filters
-----------------------

Creating custom filters can be easy, or very easy.

Before we get to that though, it is first necessary to understand that
there are two types of filters: *target filters* and *source filters*.
Target filters are the default case; they are applied the the complete
content after all the source files have been merged together. Source
filters, on the other, are applied to each source file before the result
is merged into the final target.

The usual reason to write a source filter is because the filters work
depends on knowledge of the input file path. This is true, for example,
for the :ref:`cssrewrite <filters-cssrewrite>` filter. Another example
are CSS converters like :ref:`less <filters-less>`, which support
include mechanisms that work relative to the input filename.

With that in mind...

The very easy way
-----------------

In the simplest case, a filter is simply a function what takes two
arguments, an input stream and an output stream.

.. code-block:: python

    def noop(_in, out):
        out.write(_in.read())

That's it! You can use this filter when defining your bundles:

.. code-block:: python

    bundle = Bundle('input.js', filters=(noop,))

If you are using Jinja2, you can also specify the callable inline,
provided that it is available in the context:

.. code-block:: django

    {% assets filter=(noop, 'jsmin') ... %}

It even works when using Django templates, although here, you are
of course more limited in terms of syntax; if you want to use multiple
filters, you need to combine them:

.. code-block:: django

    {% assets filter=my_filters ... %}

Just make sure that the context variable ``my_filters`` is set to
your function.

Note that you currently cannot write source filters in this way.


The easy way
------------

This works by subclassing ``django.filter.Filter``. In doing so, you
need to write a bit more code, but you'll be able to enjoy a few perks.

The ``noop`` filter from the previous example, written as a class, would
look something like this:

.. code-block:: python

    from django_assets.filter import Filter

    class NoopFilter(Filter):
        name = 'noop'

        def apply(self, _in, out):
            out.write(_in.read())

The ``apply`` function should look familiar. It's basically the callable
you are already familiar with, simply pulled inside a class.

Class-based filters have a ``name``. If you do not set this, it will be
automatically generated. In doing so, the class name is lowercased, and
a potential ``Filter`` suffix is removed.


Registering
~~~~~~~~~~~

The ``name`` wouldn't make much sense, if it couldn't be used to reference
the filter. First, you need to register the class with the system though:

.. code-block:: python

    from django_assets.filter import register_filter
    register_filter(NoopFilter)

After that, you can use the filter like you would any of the built-in ones:

.. code-block:: django

    {% assets filter='jsmin,noop' ... %}


Source filters
~~~~~~~~~~~~~~

Class-based filters can be *source filters*. Simply set the
``is_source_filter`` attribute to ``True``. This will cause your filter
to be applied once for each source file, and the signature of your
``apply`` method changes to accept both the current source file processed,
as well as the output path the file will ultimately be written to:

.. code-block:: python

    class FooFilter(Filter):
        is_source_filter = True
        def apply(self, _in, out, source_path, target_path):
            ...

Options
~~~~~~~

Class-based filters are used as instances, and as such, you can easily
define a ``__init__`` method that takes arguments. However, you should
make all parameters optional, if possible, or your filter will not be
usable through a name reference.

.. TODO: Link to the pages explaining bundles and explaining filter order

There might be another thing to consider. If a filter is specified
multiple times, which sometimes can happen unsuspectingly when bundles
are nested within each other, it will only be applied a single time.
By default, all filters of the same class are considered *the same*. In
almost all cases, this will be just fine.

However, in case you want your filter to be applicable multiple times
with different options, you can implement the ``unique`` method and
return a hashable object that represents data unique to this instance:

.. code-block:: python

    class FooFilter(Filter):
        def __init__(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs
        def unique(self):
            return self.args, self.kwargs

This will cause two instances of this filter to be both applied, as long
as the arguments given differ. Two instances with the exact same arguments
will still be considered equal.

If you want each of your filter's instances to be unique, you can simply do:

.. code-block:: python

    def unique(self):
        return id(self)

Useful helpers
~~~~~~~~~~~~~~

The ``Filter`` base class provides some useful features.

setup()
^^^^^^^

It's quite common that filters have dependencies - on other Python
libraries, external tools, etc. If you want to provide your filter
regardless of whether such dependencies are matched, and fail only
if the filter is actually used, implement a ``setup()`` method on
your filter class:

.. code-block:: python

    class FooFilter(Filter):
        def setup(self):
            import foolib
            self.foolib = foolib

        def apply(self, _in, out):
            self.foolib.convert(...)

get_config()
^^^^^^^^^^^^

Some filters will need to be configured. This can of course be done by
passing arguments into ``__init__`` as explained above, but it restricts
you to configuring your filters in code, and can be tedious if necessary
every single time the filter is used.

In some cases, it makes more sense to have an option configured globally,
like the path to an external binary. A number of the built-in filters do
this, allowing you to both specify a Django setting, or an environment
variable.

The ``Filter.get_config()`` helper provides this functionality:

.. code-block:: python

    class FooFilter(Filter):
        def setup(self):
            self.bin = self.get_config('BINARY_PATH')

This will check first the Django settings, then the environment for
``BINARY_PATH``, and raise an exception if nothing is found.

``get_config()`` allows you to specify different names for the setting
and the environment variable:

.. code-block:: python

    self.get_config(setting='ASSETS_BINARY_PATH', env='BINARY_PATH')

It also supports disabling either of the two, causing only the other to
be checked for the given name:

.. code-block:: python

    self.get_config(setting='ASSETS_BINARY_PATH', env=False)

Finally, you can easily make a value optional using the ``require``
parameter. Instead of raising an exception, ``get_config()`` then returns
``None``. For example:

.. code-block:: python

    self.java = self.get_config('JAVA_BIN', require=False) or 'java'


Abstract base classes
~~~~~~~~~~~~~~~~~~~~~~

In some cases, you might want to have a common base class for multiple
filters. You can make the base class abstract by setting ``name`` to
``None`` explicitly. However, this is currently only relevant for the
built-in filters, since your own filters will not be registered
automatically in any case.


More?
-----

You can have a look inside the ``django_assets.filter`` module source
code to see a large number of example filters.