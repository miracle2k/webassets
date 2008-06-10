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

import os
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django import template
from django_assets.templatetags.assets import AssetsNode, create_merged

def _shortpath(abspath):
    """Make an absolute path relative to the project's settings module,
    which would usually be the project directory."""
    b = os.path.dirname(os.path.normpath(os.sys.modules[settings.SETTINGS_MODULE].__file__))
    p = os.path.normpath(abspath)
    return p[len(os.path.commonprefix([b, p])):]

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--parse-templates', action='store_true',
            help='Rebuild assets found by parsing project templates instead of using the tracking database.'),
    )
    help = 'Manage assets.'
    args = 'subcommand'
    requires_model_validation = True

    def handle(self, *args, **options):
        if len(args) == 0:
            raise CommandError('You need to specify a subcommand')
        elif len(args) > 1:
            raise CommandError('Invalid number of subcommands passed: %s' % ", ".join(args))
        else:
            command = args[0]

        if command == 'rebuild':
            if options.get('parse_templates'):
                assets = self._parse_templates()
            else:
                assets = dict()

            self._rebuild_assets(assets)
        else:
            raise CommandError('Unknown subcommand: %s' % command)

    def _rebuild_assets(self, assets):
        for output, data in assets.items():
            print "building asset: %s" % output
            try:
                create_merged(data['sources'], output, data['filter'], force=True)
            except Exception, e:
                print "\tfailed, error was: %s" % e

    def _parse_templates(self):
        # build a list of template directories based on configured loaders
        template_dirs = []
        if 'django.template.loaders.filesystem.load_template_source' in settings.TEMPLATE_LOADERS:
            template_dirs.extend(settings.TEMPLATE_DIRS)
        if 'django.template.loaders.app_directories.load_template_source' in settings.TEMPLATE_LOADERS:
            from django.template.loaders.app_directories import app_template_dirs
            template_dirs.extend(app_template_dirs)

        found_assets = {}
        # find all template files
        for template_dir in template_dirs:
            for directory, _ds, files in os.walk(template_dir):
                for filename in files:
                    if filename.endswith('.html'):
                        tmpl_path = os.path.join(directory, filename)
                        print "parsing template: %s" % _shortpath(tmpl_path)
                        file = open(tmpl_path, 'rb')
                        try:
                            # parse the template for asset nodes
                            try:
                                t = template.Template(file.read())
                            except template.TemplateSyntaxError, e:
                                print self.style.ERROR('\tfailed, error was: %s'%e)
                            else:
                                for node in t:
                                    if isinstance(node, AssetsNode):
                                        # try to resolve this node's data; if we fail,
                                        # then it depends on view data and we cannot
                                        # manually rebuild it.
                                        try:
                                            output, files, filter = node.resolve()
                                        except template.VariableDoesNotExist:
                                            print self.style.ERROR('\tskipping asset %s, depends on runtime data.' % node.output)
                                        else:
                                            if not output in found_assets:
                                                print self.style.NOTICE('\tfound asset: %s' % output)
                                                found_assets[output] = {
                                                    'sources': files,
                                                    'filter': filter,
                                                }
                        finally:
                            file.close()
        return found_assets
