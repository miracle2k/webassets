"""Loaders are helper classes which will read environments and/or
bundles from a source, like a configuration file.

This can be used as an alternative to an imperative setup.
"""

import os, sys
import glob, fnmatch
import importlib

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
    pass


class PythonLoader(object):
    """Basically just a simple helper to import a Python file and
    retrieve the bundles defined there.
    """

    def __init__(self, module_name):
        sys.path.insert(0, '')  # Ensure the current directory is on the path
        try:
            try:
                self.module = import_module(module_name)
            except ImportError, e:
                raise LoaderError(e)
        finally:
            sys.path.pop()

    def load_bundles(self):
        """Load ``Bundle`` objects defined in a Python module.
        """
        bundles = []
        for name in dir(self.module):
            value = getattr(self.module, name)
            if isinstance(value, Bundle):
                bundles.append(value)
        return bundles

    def load_environment(self):
        """Load a Environment defined in a Python module.
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
