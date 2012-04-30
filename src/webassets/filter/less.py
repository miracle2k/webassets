import subprocess
from webassets.filter import Filter
from webassets.exceptions import FilterError


class LessFilter(Filter):
    """Converts `Less <http://lesscss.org/>`_ markup to real CSS.

    This depends on the NodeJS implementation of less, installable
    via npm. To use the old Ruby-based version (implemented in the
    1.x Ruby gem).
    """

    name = 'less'
    options = {
        'less': ('binary', 'LESS_BIN')
    }

    def output(self, _in, out, **kw):
        binary = self.less or 'lessc'
        args = '-'
        proc = subprocess.Popen([binary, args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(_in.read())

        # At the moment (2011-12-09), there's a bug in the current version of
        # Less that always prints an error to stdout so the returncode is the
        # only way of determining if Less is actually having a compilation
        # error.
        if proc.returncode != 0:
            raise FilterError(('less: subprocess had error: stderr=%s, ' +
                               'stdout=%s, returncode=%s') % (
                stderr, stdout, proc.returncode))

        out.write(stdout)
