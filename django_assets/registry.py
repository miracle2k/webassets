"""Global bundle registry. This is what makes bundles accessible to
template tags."""

import imp
from django.utils.importlib import import_module
from bundle import Bundle


__all__ = ('register', 'RegistryError', 'get', 'reset', 'autoload',)


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


def get(name):
    return _REGISTRY.get(name, None)


def iter():
    return _REGISTRY.iteritems()


def reset():
    """Clear the registry, start over.
    """
    global _REGISTRY
    _REGISTRY.clear()


_APPLICATIONS_LOADED = False

def autoload():
    """Find assets by looking for an ``assets`` module within each
    installed application, similar to how, e.g., the admin autodiscover
    process works. This is were this code has been adapted from, too.

    Only runs once.

    TOOD: Not thread-safe!
    TODO: Bring back to status output via callbacks?
    """
    global _APPLICATIONS_LOADED
    if _APPLICATIONS_LOADED:
        return False

    # Import this locally, so that the register module does not have
    # Django dependency by itself; The setup.py script will cause
    # us to be imported when it tries to load the version.
    from django_assets.conf import settings

    for app in settings.INSTALLED_APPS:
        # For each app, we need to look for an assets.py inside that
        # app's package. We can't use os.path here -- recall that
        # modules may be imported different ways (think zip files) --
        # so we need to get the app's __path__ and look for
        # admin.py on that path.
        #if options.get('verbosity') > 1:
        #    print "\t%s..." % app,

        # Step 1: find out the app's __path__ Import errors here will
        # (and should) bubble up, but a missing __path__ (which is
        # legal, but weird) fails silently -- apps that do weird things
        # with __path__ might need to roll their own registration.
        try:
            app_path = import_module(app).__path__
        except AttributeError:
            #if options.get('verbosity') > 1:
            #    print "cannot inspect app"
            continue

        # Step 2: use imp.find_module to find the app's assets.py.
        # For some reason imp.find_module raises ImportError if the
        # app can't be found but doesn't actually try to import the
        # module. So skip this app if its assetse.py doesn't exist
        try:
            imp.find_module('assets', app_path)
        except ImportError:
            #if options.get('verbosity') > 1:
            #    print "no assets module"
            continue

        # Step 3: import the app's assets file. If this has errors we
        # want them to bubble up.
        import_module("%s.assets" % app)
        #if options.get('verbosity') > 1:
        #    print "assets module loaded"

    _APPLICATIONS_LOADED = True
