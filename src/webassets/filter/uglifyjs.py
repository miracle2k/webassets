"""Minify Javascript using `UglifyJS <https://github.com/mishoo/UglifyJS/>`_.

UglifyJS is an external tool written for NodeJS; this filter assumes that
the ``uglifyjs`` executable is in the path. Otherwise, you may define
a ``UGLIFYJS_BIN`` setting. Additional options may be passed to ``uglifyjs``
by setting ``UGLIFYJS_EXTRA_ARGS``, which expects a list of strings.
"""

import subprocess
from webassets.exceptions import FilterError
from webassets.filter import Filter


__all__ = ('UglifySFilter',)


class UglifySFilter(Filter):

    name = 'uglifyjs'

    def setup(self):
        self.binary = self.get_config(
            'UGLIFYJS_BIN', require=False) or 'uglifyjs'
        self.extra_args = self.get_config('UGLIFYJS_EXTRA_ARGS',
                                          require=False)

    def output(self, _in, out, **kw):
        args = [self.binary]
        if self.extra_args:
            args.extend(self.extra_args)
        proc = subprocess.Popen(
            args, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(_in.read())

        if proc.returncode != 0:
            raise FilterError(('uglifyjs: subprocess had error: stderr=%s, '+
                               'stdout=%s, returncode=%s') % (
                                    stderr, stdout, proc.returncode))
        out.write(stdout)
