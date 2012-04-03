"""Compile DustJS templates to a single JavaScript file that, when
loaded in the browser, registers automatically.

"""

from webassets.filter import Filter
import subprocess
from webassets.exceptions import FilterError


__all__ = ('DustJSFilter',)


class DustJSFilter(Filter):
    """`DustJS <http://akdubya.github.com/dustjs/>`_ templates compilation
    filter.

    Takes a directory full ``.dust`` files and creates a single Javascript
    object that registers to the ``dust`` global when loaded in the browser::

        Bundle('js/templates/', filters='dustjs')

    Note that in the above example, a directory is given as the bundle
    contents, which is unusual, but required by this filter.

    This uses the ``dusty`` compiler, which is a separate project from the
    DustJS implementation. To install ``dusty`` together with LinkedIn's
    version of ``dustjs`` (the original does not support NodeJS > 0.4)::

        npm install dusty
        rm -rf node_modules/dusty/node_modules/dust
        git clone https://github.com/linkedin/dustjs node_modules/dust

    .. note::

        To generate the DustJS client-side Javascript, you can then do::

            cd node_modules/dust
            make dust
            cp dist/dist-core...js your/static/assets/path

    For compilation, set the ``DUSTY_PATH=.../node_modules/dusty/bin/dusty``.
    Optionally, set ``NODE_PATH=.../node``.
    """

    name = 'dustjs'
    options = {'dusty_path': 'DUSTY_PATH',
               'node_path': 'NODE_PATH'}

    def open(self, out, source_path, **kw):
        args = []
        if self.node_path:
            args += [self.node_path]
        args += [self.dusty_path or 'dusty']
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
