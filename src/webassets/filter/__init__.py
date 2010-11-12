"""Assets can be filtered through one or multiple filters, modifying their
contents (think minification, compression).
"""

import os, subprocess
import inspect


__all__ = ('Filter', 'CallableFilter', 'get_filter', 'register_filter',)


class NameGeneratingMeta(type):
    """Metaclass that will generate a "name" attribute based on the
    class name if none is given.
    """

    def __new__(cls, name, bases, attrs):
        try:
            Filter
        except NameError:
            # Don't generate a name for the baseclass itself.
            pass
        else:
            if not 'name' in attrs:
                filter_name = name
                if name.endswith('Filter'):
                    filter_name = filter_name[:-6]
                filter_name = filter_name.lower()
                attrs['name'] = filter_name
        return type.__new__(cls, name, bases, attrs)


class Filter(object):
    """Base class for a filter.

    Subclasses should allow the creation of an instance without any
    arguments, i.e. no required arguments for __init__(), so that the
    filter can be specified by name only. In fact, the taking of
    arguments will normally be the exception.
    """

    __metaclass__ = NameGeneratingMeta

    # Name by which this filter can be referred to. Will be generated
    # automatically for subclasses if not explicitly given.
    name = None

    def __init__(self):
        self.env = None

    def __hash__(self):
        return self.id()

    def __cmp__(self, other):
        if isinstance(other, Filter):
            return cmp(self.id(), other.id())
        return NotImplemented

    def set_environment(self, env):
        """This is called just before the filter is used.
        """
        if not self.env or self.env != env:
            self.env = env
            self.setup()

    def get_config(self, setting=False, env=None, require=True,
                   what='dependency'):
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
        i.e. 'xyz filter binary'
        """
        if env is None:
            env = setting

        assert setting or env

        value = None
        if not setting is False:
            value = self.env.config.get(setting, None)

        if value is None and not env is False:
            value = os.environ.get(env)

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
        """Unique identifer for the filter instance.

        Among other things, this is used as part of the caching key.
        It should therefore not depend on instance data, but yield
        the same result across multiple python invocations.
        """
        return hash((self.name, self.unique(),))

    def setup(self):
        """Overwrite this to have the filter to initial setup work,
        like determining whether required modules are available etc.

        Since this will only be called when the user actually
        attempts to use the filter, you can raise an error here if
        dependencies are not matched.

        Note: This may be called multiple times if one filter instance
        is used with different asset environment instances.
        """

    def input(self, _in, out):
        """Implement your actual filter here.

        This will be called for every source file.
        """

    def output(self, _in, out):
        """Implement your actual filter here.

        This will be called for every output file.
        """

    # We just declared those for demonstration purposes
    del input
    del output


class CallableFilter(Filter):
    """Helper class that create a simple filter wrapping around
    callable.
    """

    def __init__(self, callable):
        self.callable = callable

    def unique(self):
        return self.callable

    def output(self, _in, out):
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
            raise Exception('%s: subprocess returned a '
                'non-success result code: %s' % (self.name, proc.returncode))
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
    if not hasattr(f, 'input') and not hasattr(f, 'output'):
        raise TypeError('Filter lacks both an input() and output() method: %s' % f)
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
            module = __import__(module_name, {}, {}, [''])
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
