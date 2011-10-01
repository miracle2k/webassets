import os, sys
import time
import logging
from optparse import OptionParser

from webassets.loaders import PythonLoader
from webassets.bundle import get_all_bundle_files
from webassets.exceptions import BuildError
from webassets.updater import TimestampUpdater


class CommandError(Exception):
    pass


class CommandLineEnvironment():
    """Implements the core functionality for a command line frontend
    to ``webassets``, abstracted in a way to allow frameworks to
    integrate the functionality into their own tools, for example,
    as a Django management command.
    """

    def __init__(self, env, log):
        self.environment = env
        self.log = log

    def invoke(self, command):
        """Invoke ``command``, or throw a CommandError.

        This is essentially a simple validation mechanism. Feel free
        to call the individual command methods manually.
        """
        try:
            function = self.Commands[command]
        except KeyError, e:
            raise CommandError('unknown command: %s' % e)
        else:
            return function(self)

    def rebuild(self):
        """Rebuild all assets now.
        """
        if self.environment.debug != False:
            self.log.warning(
                ("Current debug option is '%s'. Building as "
                 "if in production (debug=False)") % self.environment.debug)
            self.environment.debug = False
        for to_build in self.environment:
            self.log.info("Building bundle: %s" % to_build.output)
            try:
                to_build.build(force=True)
            except BuildError, e:
                    self.log.error("Failed, error was: %s" % e)

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
                for bundle in changed_bundles:
                    self.log.info("Rebuilding asset: %s" % bundle.output)
                    try:
                        bundle.build(force=True)
                    except BuildError, e:
                        print "Failed: %s" % e
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
        'rebuild': rebuild,
        'watch': watch,
        'clean': clean,
        'check': check,
    }

def main(argv, env=None):
    """Generic version of the command line utilities, not specific to
    any framework.

    TODO: Support -c option to load from YAML config file
    """
    parser = OptionParser(usage="usage: %%prog [options] [%s]" % (
        " | ".join(CommandLineEnvironment.Commands)))
    parser.add_option("-v", dest="verbose", action="store_true",
                      help="be verbose")
    parser.add_option("-q", action="store_true", dest="quiet",
                      help="be quiet")
    if env is None:
        parser.add_option("-m", "--module", dest="module",
                          help="read environment from a Python module")
    (options, args) = parser.parse_args(argv)

    if len(args) != 1:
        parser.print_help()
        return 1

    # Setup logging
    log = logging.getLogger('webassets')
    log.setLevel(logging.DEBUG if options.verbose else (
        logging.WARNING if options.quiet else logging.INFO))
    log.addHandler(logging.StreamHandler())

    # Load the bundles we shall work with
    if env is None and options.module:
        env = PythonLoader(options.module).load_environment()

    if env is None:
        print "Error: No environment given or found. Maybe use -m?"
        return 1

    # Run the selected command
    cmd = CommandLineEnvironment(env, log)
    try:
        return cmd.invoke(args[0])
    except CommandError, e:
        print e
        return 1


def run():
    sys.exit(main(sys.argv[1:]) or 0)


if __name__ == '__main__':
    run()
