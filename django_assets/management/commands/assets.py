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
from django_assets.templatetags.assets import AssetsNode
from django_assets.merge import merge
from django_assets.tracker import get_tracker


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
        make_option('--verbosity', action='store', dest='verbosity',
            default='1', type='choice', choices=['0', '1', '2'],
            help='Verbosity level; 0=minimal output, 1=normal output, 2=all output'),
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
            if options.get('parse_templates') or not get_tracker():
                assets = self._parse_templates(options)
            else:
                assets = dict()
            self._rebuild_assets(options, assets)
        else:
            raise CommandError('Unknown subcommand: %s' % command)

    def _rebuild_assets(self, options, assets):
        for output, data in assets.items():
            if options.get('verbosity') >= 1:
                print "Building asset: %s" % output
            try:
                merge(data['sources'], output, data['filter'])
            except Exception, e:
                print self.style.ERROR("Failed, error was: %s" % e)

    def _parse_templates(self, options):
        # build a list of template directories based on configured loaders
        template_dirs = []
        if 'django.template.loaders.filesystem.load_template_source' in settings.TEMPLATE_LOADERS:
            template_dirs.extend(settings.TEMPLATE_DIRS)
        if 'django.template.loaders.app_directories.load_template_source' in settings.TEMPLATE_LOADERS:
            from django.template.loaders.app_directories import app_template_dirs
            template_dirs.extend(app_template_dirs)

        found_assets = {}
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
        if options.get('verbosity') >= 2:
            print "Parsing template: %s" % _shortpath(tmpl_path)
        file = open(tmpl_path, 'rb')
        try:
            # parse the template for asset nodes
            try:
                t = template.Template(file.read())
            except template.TemplateSyntaxError, e:
                if options.get('verbosity') >= 2:
                    print self.style.ERROR('\tfailed, error was: %s'%e)
            else:
                def _recurse_node(node):
                    if isinstance(node, AssetsNode):
                        # try to resolve this node's data; if we fail,
                        # then it depends on view data and we cannot
                        # manually rebuild it.
                        try:
                            output, files, filter = node.resolve()
                        except template.VariableDoesNotExist:
                            if options.get('verbosity') >= 2:
                                print self.style.ERROR('\tskipping asset %s, depends on runtime data.' % node.output)
                        else:
                            if not output in found_assets:
                                if options.get('verbosity') >= 2:
                                    print self.style.NOTICE('\tfound asset: %s' % output)
                                found_assets[output] = {
                                    'sources': files,
                                    'filter': filter,
                                }
                    # see Django #7430
                    for subnode in hasattr(node, 'nodelist') \
                        and node.nodelist\
                        or []:
                            _recurse_node(subnode)
                for node in t:  # don't move into _recurse_node, ``Template`` has a .nodelist attribute
                    _recurse_node(node)
        finally:
            file.close()