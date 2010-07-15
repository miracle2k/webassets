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

import logging
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError

from webassets import Bundle
from webassets.bundle import BuildError
from webassets.script import (CommandLineEnvironment,
                              CommandError as AssetCommandError)
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

    def handle(self, *args, **options):
        valid_commands = CommandLineEnvironment.Commands
        if len(args) > 1:
            raise CommandError('Invalid number of subcommands passed: %s' %
                ", ".join(args))
        elif len(args) == 0:
            raise CommandError('You need to specify a subcommand: %s' %
                               ', '.join(valid_commands))

        # Create log
        log = logging.getLogger('django-assets')
        log.setLevel({0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}[int(options.get('verbosity', 1))])
        log.addHandler(logging.StreamHandler())

        # If the user requested it, search for bundles defined in templates
        if options.get('parse_templates'):
            log.info('Searching templates...')
            # TODO: Right now, if you where to merge the use of
            # template-only assets, and assets defined in code, then
            # the later might also be generated multiple times if found
            # through parsing where they are referenced in'templates.
            # I'm not sure how to best solve this: We could of course try
            # to detect the duplicates, either by instance or by output
            # path, but maybe this check should be built into the
            # environment itself (unless there are cases where we would
            # want the environment to support duplicates, though I can't
            # think of any right now. What about conditional building, i.e.
            # subbundles that are built standalone in debug mode).
            # Random idea: Should iter(environment) only yield actual
            # buildable bundles? Because both the build() and the watch()
            # command need to go through the motions of calling iterbuild().
            # Another thought: Maybe container bundles found through
            # parsing should simply be ignored. Those seem to be the sole
            # source of potential duplicates.
            get_env().add(*self.load_from_templates())

        if len(get_env()) == 0:
            raise CommandError('No asset bundles were found. '
                'If you are defining assets directly within your '
                'templates, you want to use the --parse-templates '
                'option.')

        # Execute the requested subcommand
        cmd = CommandLineEnvironment(get_env(), log)
        try:
            cmd.invoke(args[0])
        except AssetCommandError, e:
            raise CommandError(e)

    def load_from_templates(self):
        # Using the Django loader
        bundles = DjangoLoader().load_bundles()

        # Using the Jinja loader, if available
        try:
            import jinja2
        except:
            pass
        else:
            from webassets.ext.jinja2 import Jinja2Loader

            jinja2_envs = []
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

            bundles.append(Jinja2Loader(get_django_template_dirs(), jinja2_envs))

        return bundles
