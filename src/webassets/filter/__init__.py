"""Assets can be filtered through one or multiple filters, modifying their
contents (think minification, compression).
"""

import os, subprocess
import inspect
import shlex
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
from webassets.exceptions import FilterError
from webassets.importlib import import_module


__all__ = ('Filter', 'CallableFilter', 'get_filter', 'register_filter',)


def freezedicts(obj):
    """Recursively iterate over ``obj``, supporting dicts, tuples
    and lists, and freeze ``dicts`` such that ``obj`` can be used
    with hash().
    """
    if isinstance(obj, (list, tuple)):
        return type(obj)([freezedicts(sub) for sub in obj])
    if isinstance(obj, dict):
        return frozenset(obj.iteritems())
    return obj


def smartsplit(string, sep):
    """Split while allowing escaping.

    So far, this seems to do what I expect - split at the separator,
    allow escaping via \, and allow the backslash itself to be escaped.

    One problem is that it can raise a ValueError when given a backslash
    without a character to escape. I'd really like a smart splitter
    without manually scan the string. But maybe that is exactly what should
    be done.
    """
    assert string is not None   # or shlex will read from stdin
    # shlex fails miserably with unicode input
    is_unicode = isinstance(sep, unicode)
    if is_unicode:
        string = string.encode('utf8')
    l = shlex.shlex(string, posix=True)
    l.whitespace += ','
    l.whitespace_split = True
    l.quotes = ''
    if is_unicode:
        return map(lambda s: s.decode('utf8'), list(l))
    else:
        return list(l)


class option(tuple):
    """Micro option system. I want this to remain small and simple,
    which is why this class is lower-case.

    See ``parse_options()`` and ``Filter.options``.
    """
    def __new__(cls, initarg, configvar=None, type=None):
        if configvar is None:  # If only one argument given, it is the configvar
            configvar = initarg
            initarg = None
        return tuple.__new__(cls, (initarg, configvar, type))


def parse_options(options):
    """Parses the filter ``options`` dict attribute.
    The result is a dict of ``option`` tuples.
    """
    # Normalize different ways to specify the dict items:
    #    attribute: option()
    #    attribute: ('__init__ arg', 'config variable')
    #    attribute: ('config variable,')
    #    attribute: 'config variable'
    result = {}
    for internal, external in options.items():
        if not isinstance(external, option):
            if not isinstance(external, (list, tuple)):
                external = (external,)
            external = option(*external)
        result[internal] = external
    return result


class Filter(object):
    """Base class for a filter.

    Subclasses should allow the creation of an instance without any
    arguments, i.e. no required arguments for __init__(), so that the
    filter can be specified by name only. In fact, the taking of
    arguments will normally be the exception.
    """

    # Name by which this filter can be referred to.
    name = None

    # Options the filter supports. The base class will ensure that
    # these are both accepted by __init__ as kwargs, and may also be
    # defined in the environment config, or the OS environment (i.e.
    # a setup() implementation will be generated which uses
    # get_config() calls).
    #
    # Can look like this:
    #    options = {
    #        'binary': 'COMPASS_BINARY',
    #        'plugins': option('COMPASS_PLUGINS', type=list),
    #    }
    options = {}

    def __init__(self, **kwargs):
        self.env = None
        self._options = parse_options(self.__class__.options)

        # Resolve options given directly to the filter. This
        # allows creating filter instances with options that
        # deviate from the global default.
        # TODO: can the metaclass generate a init signature?
        for attribute, (initarg, _, _) in self._options.items():
            arg = initarg if initarg is not None else attribute
            if arg in kwargs:
                setattr(self, attribute, kwargs.pop(arg))
            else:
                setattr(self, attribute, None)
        if kwargs:
            raise TypeError('got an unexpected keyword argument: %s' %
                            kwargs.keys()[0])

    def __hash__(self):
        return self.id()

    def __cmp__(self, other):
        if isinstance(other, Filter):
            return cmp(self.id(), other.id())
        return NotImplemented

    def set_environment(self, env):
        """This is called before the filter is used."""
        self.env = env

    def get_config(self, setting=False, env=None, require=True,
                   what='dependency', type=None):
        """Helper function that subclasses can use if they have
        dependencies which they cannot automatically resolve, like
        an external binary.

        Using this function will give the user the ability to  resolve
        these dependencies in a common way through either a Django
        setting, or an environment variable.

        You may specify different names for ``setting`` and ``env``.
        If only the former is given, the latter is considered to use
        the same name. If either argument is ``False``, the respective
        source is not used.

        By default, if the value is not found, an error is raised. If
        ``required`` is ``False``, then ``None`` is returned instead.

        ``what`` is a string that is used in the exception message;
        you can use it to give the user an idea what he is lacking,
        i.e. 'xyz filter binary'.

        Specifying values via the OS environment is obviously limited. If
        you are expecting a special type, you may set the ``type`` argument
        and a value from the OS environment will be parsed into that type.
        Currently only ``list`` is supported.
        """
        assert type in (None, list), "%s not supported for type" % type

        if env is None:
            env = setting

        assert setting or env

        value = None
        if not setting is False:
            value = self.env.config.get(setting, None)

        if value is None and not env is False:
            value = os.environ.get(env)
            if value and type == list:
                value = smartsplit(value, ',')

        if value is None and require:
            err_msg = '%s was not found. Define a ' % what
            options = []
            if setting:
                options.append('%s setting' % setting)
            if env:
                options.append('%s environment variable' % env)
            err_msg += ' or '.join(options)
            raise EnvironmentError(err_msg)
        return value

    def unique(self):
        """This function is used to determine if two filter instances
        represent the same filter and can be merged. Only one of the
        filters will be applied.

        If your filter takes options, you might want to override this
        and return a hashable object containing all the data unique
        to your current instance. This will allow your filter to be applied
        multiple times with differing values for those options.
        """
        return False

    def id(self):
        """Unique identifier for the filter instance.

        Among other things, this is used as part of the caching key.
        It should therefore not depend on instance data, but yield
        the same result across multiple python invocations.
        """
        # freezedicts() allows filters to return dict objects as part
        # of unique(), which are not per-se supported by hash().
        return hash((self.name, freezedicts(self.unique()),))

    def setup(self):
        """Overwrite this to have the filter do initial setup work,
        like determining whether required modules are available etc.

        Since this will only be called when the user actually
        attempts to use the filter, you can raise an error here if
        dependencies are not matched.

        Note: In most cases, it should be enough to simply define
        the ``options`` attribute. If you override this method and
        want to use options as well, don't forget to call super().

        Note: This may be called multiple times if one filter instance
        is used with different asset environment instances.
        """
        for attribute, (_, configvar, type) in self._options.items():
            if not configvar:
                continue
            if getattr(self, attribute) is None:
                # No value specified for this filter instance ,
                # specifically attempt to load it from the environment.
                setattr(self, attribute,
                    self.get_config(setting=configvar, require=False,
                                    type=type))

    def input(self, _in, out, **kw):
        """Implement your actual filter here.

        This will be called for every source file.
        """

    def output(self, _in, out, **kw):
        """Implement your actual filter here.

        This will be called for every output file.
        """

    def open(self, out, source_path, **kw):
        """Implement your actual filter here.

        This is like input(), but only one filter may provide this.
        Use this if your filter needs to read from the source file
        directly, and would ignore any processing by earlier filters.
        """

    def concat(self, out, hunks, **kw):
        """Implement your actual filter here.

       Will be called once between the input() and output()
       steps, and should concat all the source files (given as hunks)
       together, and return a string.

       Only one such filter is allowed.
       """

    # We just declared those for demonstration purposes
    del input
    del output
    del open
    del concat


class CallableFilter(Filter):
    """Helper class that create a simple filter wrapping around
    callable.
    """

    def __init__(self, callable):
        super(CallableFilter, self).__init__()
        self.callable = callable

    def unique(self):
        # XXX This means the cache will never work for those filters.
        # This is actually a deeper problem: Originally unique() was
        # used to remove duplicate filters. Now it is also for the cache
        # key. The latter would benefit from ALL the filter's options being
        # included. Possibly this might just be what we should do, at the
        # expense of the "remove duplicates" functionality (because it
        # is never really needed anyway). It's also illdefined when a filter
        # should be a removable duplicate - most options probably SHOULD make
        # a filter no longer being considered duplicate.
        return self.callable

    def output(self, _in, out, **kw):
        return self.callable(_in, out)


class JavaMixin(object):
    """Mixin for filters which use Java ARchives (JARs) to perform tasks.
    """

    def java_setup(self):
        # We can reasonably expect that java is just on the path, so
        # don't require it, but hope for the best.
        path = self.get_config(env='JAVA_HOME', require=False)
        if path is not None:
            self.java = os.path.join(path, 'bin/java')
        else:
            self.java = 'java'

    def java_run(self, _in, out, args):
        proc = subprocess.Popen(
            [self.java, '-jar', self.jar] + args,
            # we cannot use the in/out streams directly, as they might be
            # StringIO objects (which are not supported by subprocess)
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(_in.read())
        if proc.returncode:
            raise FilterError('%s: subprocess returned a '
                'non-success result code: %s, stdout=%s, stderr=%s' % (
                     self.name, proc.returncode, stdout, stderr))
            # stderr contains error messages
        else:
            out.write(stdout)


_FILTERS = {}

def register_filter(f):
    """Add the given filter to the list of know filters.
    """
    if not issubclass(f, Filter):
        raise ValueError("Must be a subclass of 'Filter'")
    if not f.name:
        raise ValueError('Must have a name')
    if f.name in _FILTERS:
        raise KeyError('Filter with name %s already registered' % f.name)
    _FILTERS[f.name] = f


def get_filter(f, *args, **kwargs):
    """Resolves ``f`` to a filter instance.

    Different ways of specifying a filter are supported, for example by
    giving the class, or a filter name.

    *args and **kwargs are passed along to the filter when it's
    instantiated.
    """
    if isinstance(f, Filter):
        # Don't need to do anything.
        assert not args and not kwargs
        return f
    elif isinstance(f, basestring):
        if f in _FILTERS:
            klass = _FILTERS[f]
        else:
            raise ValueError('No filter \'%s\'' % f)
    elif inspect.isclass(f) and issubclass(f, Filter):
        klass = f
    elif callable(f):
        assert not args and not kwargs
        return CallableFilter(f)
    else:
        raise ValueError('Unable to resolve to a filter: %s' % f)

    return klass(*args, **kwargs)


def load_builtin_filters():
    from os import path
    import warnings

    current_dir = path.dirname(__file__)
    for entry in os.listdir(current_dir):
        if entry.endswith('.py'):
            name = path.splitext(entry)[0]
        elif path.exists(path.join(current_dir, entry, '__init__.py')):
            name = entry
        else:
            continue

        module_name = 'webassets.filter.%s' % name
        try:
            module = import_module(module_name)
        except Exception, e:
            warnings.warn('Error while loading builtin filter '
                          'module \'%s\': %s' % (module_name, e))
        else:
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if inspect.isclass(attr) and issubclass(attr, Filter):
                    if not attr.name:
                        # Skip if filter has no name; those are
                        # considered abstract base classes.
                        continue
                    register_filter(attr)
load_builtin_filters()
