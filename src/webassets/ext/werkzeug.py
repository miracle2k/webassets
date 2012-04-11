import logging
import warnings
from webassets.exceptions import ImminentDeprecationWarning
from webassets.script import CommandLineEnvironment


__all__ = ('make_assets_action',)


def make_assets_action(environment, loaders=[]):
    """Creates a ``werkzeug.script`` action which interfaces
    with the webassets command line tools.

    Since Werkzeug does not provide a way to have subcommands,
    we need to model the assets subcommands as options.

    If ``loaders`` is given, the command will use these loaders
    to add bundles to the environment. This is mainly useful if
    you are defining your bundles inside templates only, and
    need to find them first using something like the Jinja2Loader.
    """

    warnings.warn('The werkzeug script integration is deprecated, '
                  'because the werkzeug.script module itself is.',
                        ImminentDeprecationWarning)

    log = logging.getLogger('webassets')
    log.addHandler(logging.StreamHandler())

    def action(rebuild=False, watch=False, check=False, clean=False,
               quiet=('q', False), verbose=('v', False)):
        if len(filter(bool, [rebuild, watch, clean, check])) != 1:
            print "Error: exactly one of --rebuild, --watch, --check or --clean must be given"
            return 1

        if rebuild:
            command = 'rebuild'
        elif watch:
            command = 'watch'
        elif clean:
            command = 'clean'
        elif check:
            command = 'check'

        log.setLevel(logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO))

        cmdenv = CommandLineEnvironment(environment, log)
        if loaders:
            log.info('Finding bundles...')
            for loader in loaders:
                environment.add(*[b for b in loader.load_bundles() if not b.is_container])

        cmdenv.invoke(command)

    return action
