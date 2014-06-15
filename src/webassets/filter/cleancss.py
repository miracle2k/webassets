import os

from webassets.filter import ExternalTool


__all__ = ('CleanCSS',)


class CleanCSS(ExternalTool):
    """
    Minify css using `Clean-css <https://github.com/GoalSmashers/clean-css/>`_.

    Clean-css is an external tool written for NodeJS; this filter assumes that
    the ``cleancss`` executable is in the path. Otherwise, you may define
    a ``CLEANCSS_BIN`` setting.
    """

    name = 'cleancss'
    options = {
        'binary': 'CLEANCSS_BIN',
    }

    def output(self, _in, out, **kw):
        self.subprocess([self.binary or 'cleancss'], out, _in)

    def input(self, _in, out, **kw):
        args = [self.binary or 'cleancss', '--root', os.path.dirname(kw['source_path'])]
        self.subprocess(args, out, _in)

