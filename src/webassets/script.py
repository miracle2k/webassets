import os, sys
import time
import logging

from webassets.loaders import PythonLoader
from webassets.bundle import get_all_bundle_files
from webassets.exceptions import BuildError, ImminentDeprecationWarning
from webassets.updater import TimestampUpdater


__all__ = ('CommandError', 'CommandLineEnvironment', 'main')


class CommandError(Exception):
    pass


class CommandLineEnvironment():
    """Implements the core functionality for a command line frontend
    to ``webassets``, abstracted in a way to allow frameworks to
    integrate the functionality into their own tools, for example,
    as a Django management command.
    """

    def __init__(self, env, log, post_build=None):
        self.environment = env
        self.log = log
        self.event_handlers = dict(post_build=lambda: True)
        if callable(post_build):
            self.event_handlers['post_build'] = post_build

    def invoke(self, command, args):
        """Invoke ``command``, or throw a CommandError.

        This is essentially a simple validation mechanism. Feel free
        to call the individual command methods manually.
        """
        try:
            function = self.Commands[command]
        except KeyError, e:
            raise CommandError('unknown command: %s' % e)
        else:
            return function(self, **args)

    def rebuild(self):
        import warnings
        warnings.warn(
            'The rebuild() method has been renamed to build().',
            ImminentDeprecationWarning)
        return self.build()

    def build(self):
        """Build/Rebuild assets.
        """
        if self.environment.debug != False:
            self.log.warning(
                ("Current debug option is '%s'. Building as "
                 "if in production (debug=False)") % self.environment.debug)
            self.environment.debug = False
        built = []
        for to_build in self.environment:
            self.log.info("Building bundle: %s" % to_build.output)
            try:
                to_build.build(force=True, env=self.environment)
                built.append(to_build)
            except BuildError, e:
                self.log.error("Failed, error was: %s" % e)
        if len(built):
            self.event_handlers['post_build']()

    def watch(self):
        """Watch assets for changes.

        TODO: This should probably also restart when the code changes.
        """
        _mtimes = {}
        _win = (sys.platform == "win32")
        def check_for_changes():
            changed_bundles = []
            for bundle in self.environment:
                for filename in get_all_bundle_files(bundle):
                    stat = os.stat(filename)
                    mtime = stat.st_mtime
                    if _win:
                        mtime -= stat.st_ctime

                    if _mtimes.get(filename, mtime) != mtime:
                        changed_bundles.append(bundle)
                        _mtimes[filename] = mtime
                        break
                    _mtimes[filename] = mtime
            return changed_bundles

        try:
            self.log.info("Watching %d bundles for changes..." % len(self.environment))
            while True:
                changed_bundles = check_for_changes()
                built = []
                for bundle in changed_bundles:
                    self.log.info("Rebuilding asset: %s" % bundle.output)
                    try:
                        bundle.build(force=True)
                        built.append(bundle)
                    except BuildError, e:
                        print "Failed: %s" % e
                if len(built):
                    self.event_handlers['post_build']()
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass

    def clean(self):
        """ Delete generated assets.

        TODO: Clean the cache?
        """
        self.log.info('Cleaning generated assets...')
        for bundle in self.environment:
            if not bundle.output:
                continue
            file_path = self.environment.abspath(bundle.output)
            if os.path.exists(file_path):
                os.unlink(file_path)
                self.log.info("Deleted asset: %s" % bundle.output)

    def check(self):
        """Check to see if assets need to be rebuilt.

        A non-zero exit status will be returned if any of the input files are
        newer (based on mtime) than their output file. This is intended to be
        used in pre-commit hooks.
        """
        needsupdate = False
        updater = self.environment.updater
        if not updater:
            self.log.debug('no updater configured, using TimestampUpdater')
            updater = TimestampUpdater()
        for bundle in self.environment:
            self.log.info('Checking asset: %s', bundle.output)
            if updater.needs_rebuild(bundle, self.environment):
                self.log.info('  needs update')
                needsupdate = True
        if needsupdate:
            sys.exit(-1)

    # List of command methods
    Commands = {
        'build': build,
        'watch': watch,
        'clean': clean,
        'check': check,
        'rebuild': rebuild,  # Deprecated
    }


class GenericArgparseImplementation(object):
    """Generic command line utility to interact with an webassets
    environment.

    This is effectively a reference implementation of a command line
    utility based on the ``CommandLineEnvironment`` class.
    Implementers may find it feasible to simple base their own command
    line utility on this, rather than implementing something custom on
    top of ``CommandLineEnvironment``. In fact, if that is possible,
    you are encouraged to do so for greater consistency across
    implementations.
    """

    def __init__(self, env, prog=None):
        try:
            import argparse
        except ImportError:
            raise RuntimeError(
                'The webassets command line now requires the '
                '"argparse" library on Python versions <= 2.6.')
        else:
            self.argparse = argparse
        self.env = env
        self._construct_parser(prog)

    def _construct_parser(self,prog=None):
        self.parser = parser = self.argparse.ArgumentParser(
            description="Manage assets.",
            prog=prog)

        # Start with the base arguments that are valid for any command.
        # XXX: Add those to the subparser?
        parser.add_argument("-v", dest="verbose", action="store_true",
            help="be verbose")
        parser.add_argument("-q", action="store_true", dest="quiet",
            help="be quiet")
        if self.env is None:
            # TODO: Support -c option to load from YAML config file
            parser.add_argument("-m", "--module", dest="module",
                help="read environment from a Python module")

        # Add subparsers.
        subparsers = parser.add_subparsers(dest='command')
        for command in CommandLineEnvironment.Commands.keys():
            command_parser = subparsers.add_parser(command)
            maker = getattr(self, 'make_%s_parser' % command, False)
            if maker:
                maker(command_parser)

    @staticmethod
    def make_build_parser(parser):
        pass

    def main(self, argv):
        """Parse the given command line.

        The command ine is expected to NOT including what would be
        sys.argv[0].
        """
        ns = self.parser.parse_args(argv)

        # Setup logging
        log = logging.getLogger('webassets')
        log.setLevel(logging.DEBUG if ns.verbose else (
            logging.WARNING if ns.quiet else logging.INFO))
        log.addHandler(logging.StreamHandler())

        # Load the bundles we shall work with
        if self.env is None and ns.module:
            env = PythonLoader(ns.module).load_environment()

        if self.env is None:
            print "Error: No environment given or found. Maybe use -m?"
            return 1

        # Prepare a dict of arguments cleaned of values that are not
        # command-specific, and which the command method would not accept.
        args = vars(ns).copy()
        for name in ('verbose', 'quiet', 'module', 'command'):
            if name in args:
                del args[name]

        # Run the selected command
        cmd = CommandLineEnvironment(self.env, log)
        try:
            return cmd.invoke(ns.command, args)
        except CommandError, e:
            print e
            return 1


def main(argv, env=None):
    """Execute the generic version of the command line interface.

    You only need to work directly with ``GenericArgparseImplementation``
    if you desire to customize things.

    If no environment is givne, additional arguments will be supported to
    allow the user to specify/construct the environment on the command line.
    """
    return GenericArgparseImplementation(env).main(argv)


def run():
    """Runs the command line interface via ``main``, then exists the
    process with the proper return code."""
    sys.exit(main(sys.argv[1:]) or 0)


if __name__ == '__main__':
    run()
