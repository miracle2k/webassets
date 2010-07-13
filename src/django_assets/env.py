from django.conf import settings
from webassets.env import Environment
from webassets.importlib import import_module


__all__ = ('register',)


class DjangoEnvironment(Environment):
    """For Django, we need to redirect all the configuration values this
    object holds to Django's own settings object.

    We do this by hooking into __getattribute__ and __setattribute__,
    rather than reimplementing the get_foo/set_foo() methods, which means
    we won't have to reimplement any validation the parent class may do.
    """

    _mapping = {
        'debug': 'ASSETS_DEBUG',
        'cache': 'ASSETS_CACHE',
        'updater': 'ASSETS_UPDATER',
        'auto_create': 'ASSETS_AUTO_CREATE',
        'expire': 'ASSETS_EXPIRE',
        'directory': 'MEDIA_ROOT',
        'url': 'MEDIA_URL',
    }

    def __init__(self):
        self.django_settings = settings

    def get_config(self, key, default=None):
        return getattr(self.django_settings, key, default)

    def __getattribute__(self, name):
        if name == '_mapping' or not name in self._mapping:
            return super(DjangoEnvironment, self).__getattribute__(name)
        return getattr(self.django_settings, self._mapping[name])

    def __setattr__(self, name, value):
        if name in self._mapping:
            setattr(self.django_settings, self._mapping[name], value)
            return
        super(DjangoEnvironment, self).__setattr__(name, value)


# Django has a global state, a global configuration, and so we need a
# global instance of a asset environment.
env = DjangoEnvironment()


# The user needn't know about the env though, we can expose the
# relevant functionality directly. This is also for backwards-compatibility
# with times where ``django-assets`` was a standalone library.
register = env.register


# Finally, we'd like to autoload the ``assets`` module of each Django.
try:
    from django.utils.importlib import import_module
except ImportError:
    # django-1.0 compatibility
    import warnings
    warnings.warn('django-assets may not be compatible with Django versions '
                  'earlier than 1.1', DeprecationWarning)
    def import_module(app):
        return __import__(app, {}, {}, [app.split('.')[-1]]).__path__


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

    # Import this locally, so that we don't have a global Django
    # dependency.
    from django.conf import settings

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