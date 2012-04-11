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

    def open(self, out, source_path, **kw):
        proc = subprocess.Popen(
            [self.less or 'lessc', source_path],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE
        )
        stdout, stderr = proc.communicate()

        # At the moment (2011-12-09), there's a bug in the current version of
        # Less that always prints an error to stdout so the returncode is the
        # only way of determining if Less is actually having a compilation
        # error.
        if proc.returncode != 0:
            raise FilterError(('less: subprocess had error: stderr=%s, ' +
                               'stdout=%s, returncode=%s') % (
                stderr, stdout, proc.returncode))

        out.write(stdout)
