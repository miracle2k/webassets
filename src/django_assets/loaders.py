from django.conf import settings
from django import template
from webassets.loaders import GlobLoader, LoaderError

try:
    set
except NameError:
    from sets import Set as set

from django_assets.templatetags.assets import AssetsNode as AssetsNodeOriginal
try:
    from django.templatetags.assets import AssetsNode as AssetsNodeMapped
except ImportError:
    # Since Django #12295, custom templatetags are no longer mapped into
    # the Django namespace. Support both versions.
    AssetsNodeMapped = None
AssetsNodeClasses = filter(lambda c: bool(c),
    (AssetsNodeOriginal, AssetsNodeMapped))


__all__ = ('DjangoLoader', 'get_django_template_dirs',)


def _shortpath(abspath):
    """Make an absolute path relative to the project's settings module,
    which would usually be the project directory.
    """
    b = os.path.dirname(os.path.normpath(sys.modules[settings.SETTINGS_MODULE].__file__))
    p = os.path.normpath(abspath)
    return p[len(os.path.commonprefix([b, p])):]


def uniq(seq):
    """Remove duplicate items, preserve order.

    http://www.peterbe.com/plog/uniqifiers-benchmark
    """
    seen = set()
    seen_add = seen.add
    return [x for x in seq if x not in seen and not seen_add(x)]


FILESYSTEM_LOADERS = [
    'django.template.loaders.filesystem.load_template_source', # <= 1.1
    'django.template.loaders.filesystem.Loader',                 # > 1.2
]
APPDIR_LOADERS = [
    'django.template.loaders.app_directories.load_template_source', # <= 1.1
    'django.template.loaders.app_directories.Loader'            # > 1.2
]
def get_django_template_dirs(loader_list=None):
    """Build a list of template directories based on configured loaders.
    """
    if not loader_list:
        loader_list = settings.TEMPLATE_LOADERS

    template_dirs = []
    for loader in loader_list:
        if loader in FILESYSTEM_LOADERS:
            template_dirs.extend(settings.TEMPLATE_DIRS)
        if loader in APPDIR_LOADERS:
            from django.template.loaders.app_directories import app_template_dirs
            template_dirs.extend(app_template_dirs)
        if isinstance(loader, (list, tuple)) and len(loader) >= 2:
            # The cached loader uses the tuple syntax, but simply search all
            # tuples for nested loaders; thus possibly support custom ones too.
            template_dirs.extend(get_django_template_dirs(loader[1]))

    return uniq(template_dirs)


class DjangoLoader(GlobLoader):
    """Parse all the templates of the current Django project, try to find
    bundles in active use.
    """

    def load_bundles(self):
        bundles = []
        for template_dir in get_django_template_dirs():
            for filename in self.glob_files((template_dir, '*.html'), True):
                bundles.extend(self.with_file(filename, self._parse) or [])
        return bundles

    def _parse(self, filename, contents):
        # parse the template for asset nodes
        try:
            t = template.Template(contents)
        except template.TemplateSyntaxError, e:
            raise LoaderError('Django parser failed: %s' % e)
        else:
            result = []
            def _recurse_node(node):
                # depending on whether the template tag is added to
                # builtins, or loaded via {% load %}, it will be
                # available in a different module
                if node is not None and \
                   isinstance(node, AssetsNodeClasses):
                    # try to resolve this node's data; if we fail,
                    # then it depends on view data and we cannot
                    # manually rebuild it.
                    try:
                        bundle = node.resolve()
                    except template.VariableDoesNotExist:
                        raise LoaderError('skipping bundle %s, depends on runtime data' % node.output)
                    else:
                        result.append(bundle)
                # see Django #7430
                for subnode in hasattr(node, 'nodelist') \
                    and node.nodelist\
                    or []:
                        _recurse_node(subnode)
            for node in t:  # don't move into _recurse_node, ``Template`` has a .nodelist attribute
                _recurse_node(node)
            return result
