"""Compile `Handlebars <http://handlebarsjs.com/>`_ templates.

This filter assumes that the ``handlebars`` executable is in the path.
Otherwise, you may define a ``HANDLEBARS_BIN`` setting.

Note: Use this filter if you want to precompile Handlebars templates.
If compiling them in the browser is acceptable, you may use the JST
filter, which needs no external dependency.
"""

import subprocess
from os import path

from webassets.exceptions import FilterError
from webassets.filter import Filter


__all__ = ('HandlebarsFilter',)


class HandlebarsFilter(Filter):

    name = 'handlebars'
    options = {
        'binary': 'HANDLEBARS_BIN',
        'extra_args': 'HANDLEBARS_EXTRA_ARGS',
        'root': 'HANDLEBARS_ROOT',
    }

    def input(self, _in, out, source_path, output_path):
        if self.root:
            root = path.join(self.get_config('directory'), self.root)
        else:
            root = self.get_config('directory')

        args = [self.binary or 'handlebars',
                '-r', root]
        if self.extra_args:
            args.extend(self.extra_args)
        args.extend([source_path])

        proc = subprocess.Popen(
            args, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.returncode != 0:
            raise FilterError(('handlebars: subprocess had error: stderr=%s, '+
                               'stdout=%s, returncode=%s') % (
                                    stderr, stdout, proc.returncode))
        out.write(stdout.strip() + ';')
