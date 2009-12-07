"""Assets can be filtered through one or multiple filters, modifying their
contents (think minification, compression).
"""

import os, re
import inspect
from django.conf import settings


__all__ = ('Filter', 'CallableFilter', 'get_filter', 'register_filter',)


class NameGeneratingMeta(type):
    """Metaclass that will generate a "name" attribute based on the
    class name if non is given.
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
        self.setup()

    def __hash__(self):
        return self.id()

    def __cmp__(self, other):
        if isinstance(other, Filter):
            return cmp(self.id(), other.id())
        return NotImplemented

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
            value = getattr(settings, setting, None)

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

    def id(self):
        return hash((id(self.__class__), self.unique(),)) or id(self)

    def setup(self):
        """Overwrite this to have the filter to initial setup work,
        like determining whether required modules are available etc.

        Since this will only be called when the user actually
        attempts to use the filter, you can raise an error here if
        dependencies are not matched.
        """

    def apply(self, _in, out):
        """Implement your actual filter here.
        """
        raise NotImplementError()


class CallableFilter(Filter):
    """Helper class that create a simple filter wrapping around
    callable.
    """

    def __init__(self, callable):
        self.callable = callable

    def unique(self):
        return self.callable

    def apply(self, _in, out):
        return self.callable(_in, out)


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


def get_filter(f):
    """Resolves ``f`` to a filter instance.

    Different ways of specifying a filter are supported, for example by
    giving the class, or a filter name.
    """
    if isinstance(f, Filter):
        # Don't need to do anything.
        return f
    elif isinstance(f, basestring):
        if f in _FILTERS:
            klass = _FILTERS[f]
        else:
            raise ValueError('No filter \'%s\'' % f)
    elif inspect.isclass(f) and issubclass(f, Filter):
        klass = f
    elif callable(f):
        return CallableFilter(f)
    else:
        raise ValueError('Unable to resolve to a filter: %s' % f)

    return klass()


def load_builtin_filters():
    from os import path
    import warnings

    current_dir = path.dirname(__file__)
    for subdir in os.listdir(current_dir):
        if path.exists(path.join(current_dir, subdir, '__init__.py')):
            module_name = 'django_assets.filter.%s' % subdir
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
del load_builtin_filters
