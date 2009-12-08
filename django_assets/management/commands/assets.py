"""Manage assets.

Usage:

    ./manage.py assets rebuild

        Rebuild all known assets; this requires tracking to be enabled:
        Only assets that have previously been built and tracked are
        considered "known".

    ./manage.py assets rebuild --parse-templates

        Try to find as many of the project's templates (hopefully all),
        and check them for the use of assets. Rebuild all the assets
        discovered in this way. If tracking is enabled, the tracking
        database will be replaced by the newly found assets.
"""

import os, imp
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django import template

from django_assets.conf import settings
from django_assets.templatetags.assets import AssetsNode as AssetsNodeOriginal
from django.templatetags.assets import AssetsNode as AssetsNodeMapped
from django_assets.merge import process
from django_assets import registry, Bundle

try:
    import jinja2
except:
    jinja2 = None
else:
    jinja2_envs = []
    from django_assets.jinja2.extension import AssetsExtension
    # Prepare a Jinja2 environment we can later use for parsing.
    # If not specified by the user, put in there at least our own
    # extension, which we will need most definitely to achieve anything.
    _jinja2_extensions = getattr(settings, 'ASSETS_JINJA2_EXTENSIONS')
    if not _jinja2_extensions:
        _jinja2_extensions = [AssetsExtension.identifier]
    jinja2_envs.append(jinja2.Environment(extensions=_jinja2_extensions))

    try:
        from coffin.common import get_env as get_coffin_env
    except:
        pass
    else:
        jinja2_envs.append(get_coffin_env())


def _shortpath(abspath):
    """Make an absolute path relative to the project's settings module,
    which would usually be the project directory."""
    b = os.path.dirname(os.path.normpath(os.sys.modules[settings.SETTINGS_MODULE].__file__))
    p = os.path.normpath(abspath)
    return p[len(os.path.commonprefix([b, p])):]


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--parse-templates', action='store_true',
            help='Rebuild assets found by parsing project templates '
                 'instead of using the tracking database.'),
    )
    help = 'Manage assets.'
    args = 'subcommand'
    requires_model_validation = True

    def handle(self, *args, **options):
        if len(args) == 0:
            raise CommandError('You need to specify a subcommand')
        elif len(args) > 1:
            raise CommandError('Invalid number of subcommands passed: %s' %
                ", ".join(args))
        else:
            command = args[0]

        options['verbosity'] = int(options['verbosity'])

        if command == 'rebuild':
            # Start with the bundles that are defined in code.
            if options.get('verbosity') > 1:
                print "Looking for bundles defined in code..."
            registry.autoload()
            bundles = [v for k, v in registry.iter()]

            # If requested, search the templates too.
            if options.get('parse_templates'):
                bundles += self._parse_templates(options)
            else:
                if not bundles:
                    raise CommandError('No asset bundles were found. '
                        'If you are defining assets directly within your '
                        'templates, you want to use the --parse-templates '
                        'option.')

            self._rebuild_assets(options, bundles)
        else:
            raise CommandError('Unknown subcommand: %s' % command)

    def _rebuild_assets(self, options, bundles):
        for bundle in bundles:
            if options.get('verbosity') >= 1:
                print "Building asset: %s" % bundle.output
            try:
                process(bundle, force=True, allow_debug=False)
            except ValueError, e:
                # TODO: It would be cool if we could only capture those
                # exceptions actually related to merging.
                print self.style.ERROR("Failed, error was: %s" % e)

    def _parse_templates(self, options):
        # build a list of template directories based on configured loaders
        template_dirs = []
        if 'django.template.loaders.filesystem.load_template_source' in settings.TEMPLATE_LOADERS:
            template_dirs.extend(settings.TEMPLATE_DIRS)
        if 'django.template.loaders.app_directories.load_template_source' in settings.TEMPLATE_LOADERS:
            from django.template.loaders.app_directories import app_template_dirs
            template_dirs.extend(app_template_dirs)

        found_assets = []
        # find all template files
        if options.get('verbosity') >= 1:
            print "Searching templates..."
        total_count = 0
        for template_dir in template_dirs:
            for directory, _ds, files in os.walk(template_dir):
                for filename in files:
                    if filename.endswith('.html'):
                        total_count += 1
                        tmpl_path = os.path.join(directory, filename)
                        self._parse_template(options, tmpl_path, found_assets)
        if options.get('verbosity') >= 1:
            print "Parsed %d templates, found %d valid assets." % (
                total_count, len(found_assets))
        return found_assets

    def _parse_template(self, options, tmpl_path, found_assets):

        def try_django(contents):
            # parse the template for asset nodes
            try:
                t = template.Template(contents)
            except template.TemplateSyntaxError, e:
                if options.get('verbosity') >= 2:
                    print self.style.ERROR('\tdjango parser failed, error was: %s'%e)
                return False
            else:
                result = []
                def _recurse_node(node):
                    # depending on whether the template tag is added to
                    # builtins, or loaded via {% load %}, it will be
                    # available in a different module
                    if isinstance(node, (AssetsNodeMapped, AssetsNodeOriginal,)):
                        # try to resolve this node's data; if we fail,
                        # then it depends on view data and we cannot
                        # manually rebuild it.
                        try:
                            bundle = node.resolve()
                        except template.VariableDoesNotExist:
                            if options.get('verbosity') >= 2:
                                print self.style.ERROR('\tskipping asset %s, depends on runtime data.' % node.output)
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

        def try_jinja(contents):
            for i, env in enumerate(jinja2_envs):
                try:
                    t = env.parse(contents.decode(settings.DEFAULT_CHARSET))
                except jinja2.exceptions.TemplateSyntaxError, e:
                    if options.get('verbosity') >= 2:
                        print self.style.ERROR('\tjinja parser (env %d) failed, error was: %s'% (i, e))
                else:
                    result = []
                    def _recurse_node(node_to_search):
                        for node in node_to_search.iter_child_nodes():
                            if isinstance(node, jinja2.nodes.Call):
                                if isinstance(node.node, jinja2.nodes.ExtensionAttribute)\
                                   and node.node.identifier == AssetsExtension.identifier:
                                    filter, output, files = node.args
                                    bundle = Bundle(
                                        *files.as_const(), **{
                                            'output': output.as_const(),
                                            'filters': filter.as_const()})
                                    result.append(bundle)
                            else:
                                _recurse_node(node)
                    for node in t.iter_child_nodes():
                        _recurse_node(node)
                    return result
            return False

        if options.get('verbosity') >= 2:
            print "Parsing template: %s" % _shortpath(tmpl_path)
        file = open(tmpl_path, 'rb')
        try:
            contents = file.read()
        finally:
            file.close()

        result = try_django(contents)
        if result is False and jinja2:
            result = try_jinja(contents)
        if result:
            for bundle in result:
                if options.get('verbosity') >= 2:
                    print self.style.NOTICE('\tfound asset: %s' % bundle.output)
                found_assets.append(bundle)
