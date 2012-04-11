import os, sys
import time
import logging
from webassets.version import get_manifest

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from webassets.loaders import PythonLoader
from webassets.bundle import get_all_bundle_files
from webassets.exceptions import BuildError, ImminentDeprecationWarning
from webassets.updater import TimestampUpdater
from webassets.merge import MemoryHunk


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

    def build(self, bundles=None, output=None, directory=None, no_cache=None,
              manifest=None):
        """Build/Rebuild assets.

        ``bundles``
            A list of bundle names. If given, only this list of bundles
            should be built.

        ``output``
            List of (bundle, filename) 2-tuples. If given, only these
            bundles will be built, using the custom output filenames.
            Cannot be used with ``bundles``.

        ``directory``
            Custom output directory to use for the bundles. The original
            basenames defined in the bundle ``output`` attribute will be
            used. If the ``output`` of the bundles are pointing to different
            directories, they will be offset by their common prefix.
            Cannot be used with ``output``.

        ``no_cache``
            If set, a cache (if one is configured) will not be used.

        ``manifest``
            If set, the given manifest instance will be used, instead of
            any that might have been configured in the Environment. The value
            passed will be resolved through ``get_manifest()``. If this fails,
            a file-based manifest will be used using the given value as the
            filename.
        """
        if self.environment.debug != False:
            self.log.warning(
                ("Current debug option is '%s'. Building as "
                 "if in production (debug=False)") % self.environment.debug)
            self.environment.debug = False

        # Validate arguments
        if bundles and output:
            raise CommandError(
                'When specifying explicit output filenames you must '
                'do so for all bundles you want to build.')
        if directory and output:
            raise CommandError('A custom output directory cannot be '
                               'combined with explicit output filenames '
                               'for individual bundles.')

        # TODO: Oh how nice it would be to use the future options stack.
        if manifest is not None:
            try:
                manifest = get_manifest(manifest, env=self.environment)
            except ValueError:
                manifest = get_manifest(
                    # abspath() is important, or this will be considered
                    # relative to Environment.directory.
                    "file:%s" % os.path.abspath(manifest),
                    env=self.environment)
            self.environment.manifest = manifest

        # Use output as a dict.
        if output:
            output = dict(output)

        # Validate bundle names
        bundle_names = bundles if bundles else (output.keys() if output else [])
        for name in bundle_names:
            if not name in self.environment:
                raise CommandError(
                    'I do not know a bundle name named "%s".' % name)

        # Make a list of bundles to build, and the filename to write to.
        if bundle_names:
            # TODO: It's not ok to use an internal property here.
            bundles = [(n,b) for n, b in self.environment._named_bundles.items()
                       if n in bundle_names]
        else:
            # Includes unnamed bundles as well.
            bundles = [(None, b) for b in self.environment]

        # Determine common prefix for use with ``directory`` option.
        if directory:
            prefix = os.path.commonprefix(
                [os.path.normpath(self.environment.abspath(b.output))
                 for _, b in bundles if b.output])
            # dirname() gives the right value for a single file.
            prefix = os.path.dirname(prefix)

        to_build = []
        for name, bundle in bundles:
            # TODO: We really should support this. This error here
            # is just in place of a less understandable error that would
            # otherwise occur.
            if bundle.is_container and directory:
                raise CommandError(
                    'A custom output directory cannot currently be '
                    'used with container bundles.')

            # Determine which filename to use, if not the default.
            overwrite_filename = None
            if output:
                overwrite_filename = output[name]
            elif directory:
                offset = os.path.normpath(self.environment.abspath(
                    bundle.output))[len(prefix)+1:]
                overwrite_filename = os.path.join(directory, offset)
            to_build.append((bundle, overwrite_filename, name,))

        # Build.
        built = []
        for bundle, overwrite_filename, name in to_build:
            if name:
                # A name is not necessary available of the bundle was
                # registered without one.
                self.log.info("Building bundle: %s (to %s)" % (
                    name, overwrite_filename or bundle.output))
            else:
                self.log.info("Building bundle: %s" % bundle.output)

            try:
                if not overwrite_filename:
                    bundle.build(force=True, env=self.environment,
                                 disable_cache=no_cache)
                else:
                    # TODO: Rethink how we deal with container bundles here.
                    # As it currently stands, we write all child bundles
                    # to the target output, merged (which is also why we
                    # create and force writing to a StringIO instead of just
                    # using the ``Hunk`` objects that build() would return
                    # anyway.
                    output = StringIO()
                    bundle.build(force=True, env=self.environment, output=output,
                                 disable_cache=no_cache)
                    if directory:
                        # Only auto-create directories in this mode.
                        output_dir = os.path.dirname(overwrite_filename)
                        if not os.path.exists(output_dir):
                            os.makedirs(output_dir)
                    MemoryHunk(output.getvalue()).save(overwrite_filename)
                built.append(bundle)
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
        """Delete generated assets.

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

    def __init__(self, env=None, log=None, prog=None, no_global_options=False):
        try:
            import argparse
        except ImportError:
            raise RuntimeError(
                'The webassets command line now requires the '
                '"argparse" library on Python versions <= 2.6.')
        else:
            self.argparse = argparse
        self.env = env
        self.log = log
        self._construct_parser(prog, no_global_options)

    def _construct_parser(self, prog=None, no_global_options=False):
        self.parser = parser = self.argparse.ArgumentParser(
            description="Manage assets.",
            prog=prog)

        if not no_global_options:
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
        parser.add_argument(
            'bundles', nargs='*', metavar='BUNDLE',
            help='Optional bundle names to process. If none are '
                 'specified, then all known bundles will be built.')
        parser.add_argument(
            '--output', '-o', nargs=2, action='append',
            metavar=('BUNDLE', 'FILE'),
            help='Build the given bundle, and use a custom output '
                 'file. Can be given multiple times.')
        parser.add_argument(
            '--directory', '-d',
            help='Write built files to this directory, using the '
                 'basename defined by the bundle. Will offset '
                 'the original bundle output paths on their common '
                 'prefix. Cannot be used with --output.')
        parser.add_argument(
            '--no-cache', action='store_true',
            help='Do not use a cache that might be configured.')
        parser.add_argument(
            '--manifest',
            help='Write a manifest to the given file. Also supports '
                 'the id:arg format, if you want to use a different '
                 'manifest implementation.')

    def run_with_argv(self, argv):
        try:
            ns = self.parser.parse_args(argv)
        except SystemExit:
            # We do not want the main() function to exit the program.
            # See run() instead.
            return 1

        # Setup logging
        if self.log:
            log = self.log
        else:
            log = logging.getLogger('webassets')
            log.setLevel(logging.DEBUG if ns.verbose else (
                logging.WARNING if ns.quiet else logging.INFO))
            log.addHandler(logging.StreamHandler())

        # Load the bundles we shall work with
        if self.env is None and getattr(ns, 'module', None):
            env = PythonLoader(ns.module).load_environment()
        else:
            env = self.env

        if env is None:
            print "Error: No environment given or found. Maybe use -m?"
            return 1

        # Prepare a dict of arguments cleaned of values that are not
        # command-specific, and which the command method would not accept.
        args = vars(ns).copy()
        for name in ('verbose', 'quiet', 'module', 'command'):
            if name in args:
                del args[name]

        # Run the selected command
        cmd = CommandLineEnvironment(env, log)
        return cmd.invoke(ns.command, args)

    def main(self, argv):
        """Parse the given command line.

        The command ine is expected to NOT including what would be
        sys.argv[0].
        """
        try:
            self.run_with_argv(argv)
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
