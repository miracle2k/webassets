.. _custom-filters:

-----------------------
Creating custom filters
-----------------------

Creating custom filters can be easy, or very easy.

Before we get to that though, it is first necessary to understand that
there are two types of filters: *input filters* and *output filters*.
Output filters are applied after the complete content after all a bundle's
contents have been merged together. Input filters, on the other hand, are
applied to each source file after it is read from the disk. In the case
of nested bundles, input filters will be passed down, with the input filters 
of a parent bundle are applied before the output filter of a child bundle:

.. code-block:: python

    child_bundle = Bundle('file.css', filters='yui_css')
    Bundle(child_bundle, filters='cssrewrite')

In this example, because cssrewrite acts as an input filter, what will
essentially happen is:

.. code-block:: python

    yui_css(cssrewrite(file.css))

To be even more specific, since a single filter can act as both an input
and an output filter, the call chain will actually look something like
this:

.. code-block:: python

    cssrewrite.output(yui_css.output((cssrewrite.input((yui_css.input(file.css)))))

The usual reason to use an input filter is that the filter's
transformation depends on the source file's filename. For example,
the :ref:`cssrewrite <filters-cssrewrite>` filter needs to know the
location of the source file relative to the final output file, so it
can properly update relative references. Another example
are CSS converters like :ref:`less <filters-less>`, which 
work relative to the input filename.

With that in mind...

The very easy way
-----------------

In the simplest case, a filter is simply a function that takes two
arguments, an input stream and an output stream.

.. code-block:: python

    def noop(_in, out, **kw):
        out.write(_in.read())

That's it! You can use this filter when defining your bundles:

.. code-block:: python

    bundle = Bundle('input.js', filters=(noop,))

If you are using Jinja2, you can also specify the callable inline,
provided that it is available in the context:

.. code-block:: django

    {% assets filters=(noop, 'jsmin') ... %}

It even works when using Django templates, although here, you are
of course more limited in terms of syntax; if you want to use multiple
filters, you need to combine them:

.. code-block:: django

    {% assets filters=my_filters ... %}

Just make sure that the context variable ``my_filters`` is set to
your function.

Note that you currently cannot write input filters in this way. Callables
always act as output filters.


The easy way
------------

This works by subclassing ``webassets.filter.Filter``. In doing so, you
need to write a bit more code, but you'll be able to enjoy a few perks.

The ``noop`` filter from the previous example, written as a class, would
look something like this:

.. code-block:: python

    from webassets.filter import Filter

    class NoopFilter(Filter):
        name = 'noop'

        def output(self, _in, out, **kwargs):
            out.write(_in.read())

        def input(self, _in, out, **kwargs):
            out.write(_in.read())

The ``output`` and ``input`` methods should look familiar. They're basically
like the callable you are already familiar with, simply pulled inside a class.

Class-based filters have a ``name`` attribute, which you need to set if you
want to register your filter globally.

The ``input`` method will be called for every source file, the ``output``
method will be applied once after a bundle's contents have been concatenated.

Among the ``kwargs`` you currently receive are:

- ``source_path`` (only for ``input()``): The filename behind the ``in``
  stream, though note that other input filters may already have transformed
  it.

- ``output_path``: The final output path that your filters work will
  ultimatily end up in.

.. note::

   Always make your filters accept arbitrary ``**kwargs``. The API does allow
   for additional values to be passed along in the future.

Registering
~~~~~~~~~~~

The ``name`` wouldn't make much sense, if it couldn't be used to reference
the filter. First, you need to register the class with the system though:

.. code-block:: python

    from webassets.filter import register_filter
    register_filter(NoopFilter)

Or if you are using yaml then use the filters key for the environment:

.. code-block:: yaml

    directory: .
    url: /
    debug: True
    updater: timestamp
    filters:
        - my_custom_package.my_filter

After that, you can use the filter like you would any of the built-in ones:

.. code-block:: django

    {% assets filters='jsmin,noop' ... %}


Options
~~~~~~~

Class-based filters are used as instances, and as such, you can easily
define a ``__init__`` method that takes arguments. However, you should
make all parameters optional, if possible, or your filter will not be
usable through a name reference.

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

options
^^^^^^^

Some filters will need to be configured. This can of course be done by
passing arguments into ``__init__`` as explained above, but it restricts
you to configuring your filters in code, and can be tedious if necessary
every single time the filter is used.

In some cases, it makes more sense to have an option configured globally,
like the path to an external binary. A number of the built-in filters do
this, allowing you to both specify a config variable in the webassets
``Environment`` instance, or as an OS environment variable.

.. code-block:: python

    class FooFilter(Filter):
        options = {
            'binary': 'FOO_BIN'
        }

If you define a an ``options`` attribute on your filter class, these
options will automatically be supported both by your filter's __init__,
as well as via a configuration or environment variable. In the example
above, you may pass ``binary`` when creating a filter instance manually,
or define ``FOO_BIN`` in ``Environment.config``, or as an OS environment
variable.


get_config()
^^^^^^^^^^^^

In cases where the declarative approach of the ``options`` attribute is
not enough, you can implement custom options yourself using the
``Filter.get_config()`` helper:

.. code-block:: python

    class FooFilter(Filter):
        def setup(self):
            self.bin = self.get_config('BINARY_PATH')

This will check first the configuration, then the environment for
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

You can have a look inside the ``webassets.filter`` module source
code to see a large number of example filters.

.. automodule:: webassets.filter
