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

    ./manage.py assets watch

        Like rebuild, but continues to watch for changes, and rebuilds
        assets right away. Useful for cases where building takes some
        time.
"""

import sys
from os import path
import logging
from optparse import make_option
from django.conf import settings
from django.core.management import LaxOptionParser
from django.core.management.base import BaseCommand, CommandError

from webassets.script import (CommandError as AssetCommandError,
                              GenericArgparseImplementation)
from django_assets.env import get_env, autoload
from django_assets.loaders import get_django_template_dirs, DjangoLoader


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--parse-templates', action='store_true',
            help='Rebuild assets found by parsing project templates '
                 'instead of using the tracking database.'),
    )
    help = 'Manage assets.'
    args = 'subcommand'
    requires_model_validation = False

    def create_parser(self, prog_name, subcommand):
        # Overwrite parser creation with a LaxOptionParser that will
        # ignore arguments it doesn't know, allowing us to pass those
        # along to the webassets command.
        # Hooking into run_from_argv() would be another thing to try
        # if this turns out to be problematic.
        return LaxOptionParser(prog=prog_name,
            usage=self.usage(subcommand),
            version=self.get_version(),
            option_list=self.option_list)

    def handle(self, *args, **options):
        # Due to the use of LaxOptionParser ``args`` now contains all
        # unparsed options, and ``options`` those that the Django command
        # has declared.

        # Create log
        log = logging.getLogger('django-assets')
        log.setLevel({0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}[int(options.get('verbosity', 1))])
        log.addHandler(logging.StreamHandler())

        # If the user requested it, search for bundles defined in templates
        if options.get('parse_templates'):
            log.info('Searching templates...')
            # Note that we exclude container bundles. By their very nature,
            # they are guaranteed to have been created by solely referencing
            # other bundles which are already registered.
            get_env().add(*[b for b in self.load_from_templates()
                            if not b.is_container])

        if len(get_env()) == 0:
            raise CommandError('No asset bundles were found. '
                'If you are defining assets directly within your '
                'templates, you want to use the --parse-templates '
                'option.')

        prog = "%s assets" % path.basename(sys.argv[0])
        impl = GenericArgparseImplementation(
            env=get_env(), log=log, no_global_options=True, prog=prog)
        try:
            impl.run_with_argv(args)
        except AssetCommandError, e:
            raise CommandError(e)

    def load_from_templates(self):
        # Using the Django loader
        bundles = DjangoLoader().load_bundles()

        # Using the Jinja loader, if available
        try:
            import jinja2
        except ImportError:
            pass
        else:
            from webassets.ext.jinja2 import Jinja2Loader, AssetsExtension

            jinja2_envs = []
            # Prepare a Jinja2 environment we can later use for parsing.
            # If not specified by the user, put in there at least our own
            # extension, which we will need most definitely to achieve anything.
            _jinja2_extensions = getattr(settings, 'ASSETS_JINJA2_EXTENSIONS', False)
            if not _jinja2_extensions:
                _jinja2_extensions = [AssetsExtension.identifier]
            jinja2_envs.append(jinja2.Environment(extensions=_jinja2_extensions))

            try:
                from coffin.common import get_env as get_coffin_env
            except ImportError:
                pass
            else:
                jinja2_envs.append(get_coffin_env())

            bundles.extend(Jinja2Loader(get_env(),
                                        get_django_template_dirs(),
                                        jinja2_envs).load_bundles())

        return bundles
