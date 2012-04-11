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
from webassets.filter.jst import JSTemplateFilter
from webassets.merge import FileHunk


__all__ = ('HandlebarsFilter',)


class HandlebarsFilter(JSTemplateFilter):

    name = 'handlebars'
    options = {
        'binary': 'HANDLEBARS_BIN',
        'extra_args': 'HANDLEBARS_EXTRA_ARGS',
        'root': 'HANDLEBARS_ROOT',
    }

    # XXX Due to the way this filter works, any other filters applied
    # WILL BE IGNORED. Maybe this method should be allowed to return True
    # to indicate that the input() processor is not supported.
    def open(self, out, source_path, **kw):
        self.templates.append(source_path)
        # Write back or the cache would not detect changes
        out.write(FileHunk(source_path).data())

    def output(self, _in, out, **kw):
        if self.root is True:
            root = self.get_config('directory')
        elif self.root:
            root = path.join(self.get_config('directory'), self.root)
        else:
            root = self._find_base_path(self.templates)

        args = [self.binary or 'handlebars']
        if root:
            args.extend(['-r', root])
        if self.extra_args:
            args.extend(self.extra_args)
        args.extend(self.templates)

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
