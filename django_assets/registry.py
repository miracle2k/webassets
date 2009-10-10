"""Global bundle registry. This is what makes bundles accessible to
template tags."""

from bundle import Bundle


__all__ = ('register',)


_REGISTRY = {}


def register(name, *args):
    """Register a bundle with the given name.

    There are two possible ways to call this:

      - With a single argument:

          register('jquery', jquery_bundle)

      - With multiple arguments, automatically creating a new
        bundle inline:

          register('all.js', jquery_bundle, 'common.js', output='packed.js')
    """
    if len(args) == 0:
        raise TypeError('at least two arguments are required')
    else:
        if len(args) == 1:
            bundle = args[0]
        else:
            bundle = Bundle(args)

        global _REGISTRY
        _REGISTRY[name] = bundle