import os, subprocess

from webassets.filter import Filter
from webassets.exceptions import FilterError, ImminentDeprecationWarning


__all__ = ('CoffeeScriptFilter',)


class CoffeeScriptFilter(Filter):
    """Converts `CoffeeScript <http://jashkenas.github.com/coffee-script/>`_
    to real JavaScript.

    If you want to combine it with other JavaScript filters, make sure this
    one runs first.

    Supported configuration options:

    COFFEE_NO_BARE
        Set to ``True`` to compile without the top-level function
        wrapper (corresponds to the --bare option to ``coffee``).
    """

    name = 'coffeescript'
    options = {
        'coffee_deprecated': (False, 'COFFEE_PATH'),
        'coffee_bin': ('binary', 'COFFEE_BIN'),
        'no_bare': 'COFFEE_NO_BARE',
    }

    def input(self, _in, out, source_path, output_path, **kw):
        old_dir = os.getcwd()
        os.chdir(os.path.dirname(source_path))
        try:
            binary = self.coffee_bin or self.coffee_deprecated or 'coffee'
            if self.coffee_deprecated:
                import warnings
                warnings.warn(
                    'The COFFEE_PATH option of the "coffeescript" '
                    +'filter has been deprecated and will be removed.'
                    +'Use COFFEE_BIN instead.', ImminentDeprecationWarning)

            args = "-p" + ("" if self.no_bare else 'b')
            proc = subprocess.Popen([binary, args, source_path],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                raise FilterError(('coffeescript: subprocess had error: stderr=%s, '+
                                   'stdout=%s, returncode=%s') % (
                                                stderr, stdout, proc.returncode))
            elif stderr:
                print "coffeescript filter has warnings:", stderr
            out.write(stdout)
        finally:
            os.chdir(old_dir)
