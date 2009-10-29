"""Global bundle registry. This is what makes bundles accessible to
template tags."""

from bundle import Bundle


__all__ = ('register', 'RegistryError', 'reset')


_REGISTRY = {}


class RegistryError(Exception):
    pass


def register(name, *args, **kwargs):
    """Register a bundle with the given name.

    There are two possible ways to call this:

      - With a single ``Bundle`` instance argument:

          register('jquery', jquery_bundle)

      - With one or multiple arguments, automatically creating a
        new bundle inline:

          register('all.js', jquery_bundle, 'common.js', output='packed.js')
    """
    if len(args) == 0:
        raise TypeError('at least two arguments are required')
    else:
        if len(args) == 1 and not kwargs and isinstance(args[0], Bundle):
            bundle = args[0]
        else:
            bundle = Bundle(*args, **kwargs)

        global _REGISTRY
        if name in _REGISTRY:
            if _REGISTRY[name] == bundle:
                pass  # ignore
            else:
                raise RegistryError('Another bundle is already registered '+
                                    'as "%s": %s' % (name, _REGISTRY[name]))
        else:
            _REGISTRY[name] = bundle


def iter():
    return _REGISTRY.iteritems()


def reset():
    """Clear the registry, start over.
    """
    global _REGISTRY
    _REGISTRY.clear()