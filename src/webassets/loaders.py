"""Loaders are helper classes which will read environments and/or
bundles from a source, like a configuration file.

This can be used as an alternative to an imperative setup.
"""

import os, sys
from os import path
import glob, fnmatch
import types
try:
    import yaml
except ImportError:
    pass

from webassets import Environment
from webassets.bundle import Bundle
from webassets.importlib import import_module


__all__ = ('Loader', 'LoaderError', 'PythonLoader', 'YAMLLoader',
           'GlobLoader',)



class LoaderError(Exception):
    """Loaders should raise this when they can't deal with a given file.
    """


class YAMLLoader(object):
    """Will load bundles from a YAML configuration file.
    """

    def __init__(self, file_or_filename):
        try:
            yaml
        except NameError:
            raise EnvironmentError('PyYAML is not installed')
        else:
            self.yaml = yaml
        self.file_or_filename = file_or_filename

    def _yield_bundle_contents(self, data):
        """Yield bundle contents from the given dict.

        Each item yielded will be either a string representing a file path
        or a bundle."""
        contents = data.get('contents', [])
        if isinstance(contents, basestring):
            contents = contents,
        for content in contents:
            if isinstance(content, dict):
                content = self._get_bundle(content)
            yield content

    def _get_bundle(self, data):
        """Return a bundle initialised by the given dict."""
        kwargs = dict(
            filters=data.get('filters', None),
            output=data.get('output', None),
            debug=data.get('debug', None))
        return Bundle(*list(self._yield_bundle_contents(data)), **kwargs)

    def _get_bundles(self, obj):
        """Return a dict that keys bundle names to bundles."""
        bundles = {}
        for key, data in obj.iteritems():
            if data is None:
                data = {}
            bundles[key] = self._get_bundle(data)

        # now we need to recurse through the bundles and get any that
        # are included in each other.
        for bundle_name, bundle in bundles.items():
            # copy contents
            contents = list(bundle.contents)
            for i, item in enumerate(bundle.contents):
                if item in bundles:
                    contents[i] = bundles[item]
            # cast back to a tuple
            contents = tuple(contents)
            if contents != bundle.contents:
                bundle.contents = contents
        return bundles

    def _open(self):
        """Returns a (fileobj, filename) tuple.

        The filename can be False if it is unknown.
        """
        if isinstance(self.file_or_filename, basestring):
            return open(self.file_or_filename), self.file_or_filename

        file = self.file_or_filename
        return file, getattr(file, 'name', False)

    def load_bundles(self):
        """Load a list of ``Bundle`` instances defined in the YAML
        file.

        Expects the following format::

            bundle-name:
                filters: sass,cssutils
                output: cache/default.css
                contents:
                    - css/jquery.ui.calendar.css
                    - css/jquery.ui.slider.css
        """
        # TODO: Support a "consider paths relative to YAML location, return
        # as absolute paths" option?
        f, _ = self._open()
        try:
            obj = self.yaml.load(f) or {}
            return self._get_bundles(obj)
        finally:
            f.close()

    def load_environment(self):
        """Load an ``Environment`` instance defined in the YAML file.

        Expects the following format::

            directory: ../static
            url: /media
            debug: True
            updater: timestamp
            config:
                compass_bin: /opt/compass
                another_custom_config_value: foo

            bundles:
                bundle-name:
                    filters: sass,cssutils
                    output: cache/default.css
                    contents:
                        - css/jquery.ui.calendar.css
                        - css/jquery.ui.slider.css
        """
        f, filename = self._open()
        try:
            obj = self.yaml.load(f) or {}

            # construct the environment
            if not 'url' in obj or not 'directory' in obj:
                raise LoaderError('"url" and "directory" must be defined')
            directory = obj['directory']
            if filename:
                # If we know the location of the file, make sure that the
                # paths included are considered relative to the file location.
                directory = path.normpath(path.join(path.dirname(filename), directory))
            env = Environment(directory, obj['url'])

            # load environment settings
            for setting in ('debug', 'cache', 'versions', 'url_expire',
                            'auto_build',
                            # TODO: The deprecated values; remove at some point
                            'expire', 'updater'):
                if setting in obj:
                    setattr(env, setting, obj[setting])

            # load custom config options
            if 'config' in obj:
                env.config.update(obj['config'])

            # load bundles
            bundles = self._get_bundles(obj.get('bundles', {}))
            for name, bundle in bundles.iteritems():
                env.register(name, bundle)

            return env
        finally:
            f.close()


class PythonLoader(object):
    """Basically just a simple helper to import a Python file and
    retrieve the bundles defined there.
    """

    def __init__(self, module_name):
        if isinstance(module_name, types.ModuleType):
            self.module = module_name
        else:
            sys.path.insert(0, '')  # Ensure the current directory is on the path
            try:
                try:
                    self.module = import_module(module_name)
                except ImportError, e:
                    raise LoaderError(e)
            finally:
                sys.path.pop(0)

    def load_bundles(self):
        """Load ``Bundle`` objects defined in the Python module.

        Collects all bundles in the global namespace.
        """
        bundles = {}
        for name in dir(self.module):
            value = getattr(self.module, name)
            if isinstance(value, Bundle):
                bundles[name] = value
        return bundles

    def load_environment(self):
        """Load an ``Environment`` defined in the Python module.

        Expects a global name ``environment`` to be defined.
        """
        try:
            return getattr(self.module, 'environment')
        except AttributeError, e:
            raise LoaderError(e)


def recursive_glob(treeroot, pattern):
    """
    From:
    http://stackoverflow.com/questions/2186525/2186639#2186639
    """
    results = []
    for base, dirs, files in os.walk(treeroot):
        goodfiles = fnmatch.filter(files, pattern)
        results.extend(os.path.join(base, f) for f in goodfiles)
    return results


class GlobLoader(object):
    """Base class with some helpers for loaders which need to search
    for files.
    """

    def glob_files(self, f, recursive=False):
        if isinstance(f, tuple):
            return iter(recursive_glob(f[0], f[1]))
        else:
            return iter(glob.glob(f))

    def with_file(self, filename, then_run):
        """Call ``then_run`` with the file contents.
        """
        file = open(filename, 'r')
        try:
            contents = file.read()
            try:
                return then_run(filename, contents)
            except LoaderError:
                # We can't handle this file.
                pass
        finally:
            file.close()
