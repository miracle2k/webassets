import subprocess
from webassets.filter import Filter
from webassets.exceptions import FilterError


class NodeLessFilter(Filter):
    """Converts `Less <http://lesscss.org/>`_ markup to real CSS.

    This depends on the NodeJS implementation of less, installable
    via npm. To use the old Ruby-based version (implemented in the
    1.x Ruby gem).

    **Note**: Currently, this needs to be the very first filter
    applied. Changes by filters that ran before will be lost.
    """

    name = 'less'

    def setup(self):
        self.less = self.get_config('LESS_BIN', what='less binary',
            require=False)

    def input(self, _in, out, source_path, output_path):
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
