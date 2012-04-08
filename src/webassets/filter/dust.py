"""Compile DustJS templates to a single JavaScript file that, when
loaded in the browser, registers automatically.

"""

import os
import re
from webassets.filter import Filter
from webassets.utils import common_path_prefix
import subprocess


__all__ = ('DustJSFilter',)


class DustJSFilter(Filter):
    """`DustJS <http://akdubya.github.com/dustjs/>`_ templates
    compilation filter.

    Takes a directory fullf ``.dust`` files and creates a single
    javascript object that registers to the ``dust`` global when
    loaded in the browser.

    This uses the ``dusty`` compiler.

    To install LinkedIn's version of dustjs (with node +0.4), and
    the dusty compiler:

      npm install dusty
      rm -rf node_modules/dusty/node_modules/dust
      git clone https://github.com/linkedin/dustjs node_modules/dust

    You can then go in:

      cd node_modules/dust
      make dust
      cp dist/dist-core...js your/static/assets/path

    For compilation, set the DUSTY_PATH=.../node_modules/dusty/bin/dusty
    Optionally, set NODE_PATH=.../node

    THIS FILTER WILL IGNORE PREVIOUS FILTERS, as it imports everything
    not from the input file, but from the files in the source directory.

    So as source input, use the directory where the *.dust files are
    located.

    """
    name = 'dustjs'

    options = {'dusty_path': 'DUSTY_PATH',
               'node_path': 'NODE_PATH'}

    def open(self, out, source_path, **kw):
        args = []
        if self.node_path:
            args += [self.node_path]
        args += [self.dusty_path or 'node_modules/dusty/bin/dusty']
        # no need for --single, as we output to STDOUT
        args += [source_path]

        proc = subprocess.Popen(
            args, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.returncode != 0:
            raise FilterError(('dusty: subprocess had error: stderr=%s,' +
                               'stdout=%s, returncode=%s') % (
                                    stderr, stdout, proc.returncode))
        out.write(stdout)
