import subprocess
from webassets.exceptions import FilterError
from webassets.filter import Filter


__all__ = ('CleanCSSFilter',)


class CleanCSSFilter(Filter):
    """
    Minify Javascript using `Clean-css <https://github.com/GoalSmashers/clean-css/>`_.

    Clean-css is an external tool written for NodeJS; this filter assumes that
    the ``cleancss`` executable is in the path. Otherwise, you may define
    a ``CLEANCSS_BIN`` setting.
    """

    name = 'cleancss'
    options = {
        'binary': 'CLEANCSS_BIN',
    }

    def output(self, _in, out, **kw):
        args = [self.binary or 'cleancss']
        proc = subprocess.Popen(
            args, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(_in.read())

        if proc.returncode != 0:
            raise FilterError(('cleancss: subprocess had error: stderr=%s, '+
                               'stdout=%s, returncode=%s') % (
                                    stderr, stdout, proc.returncode))
        out.write(stdout)
