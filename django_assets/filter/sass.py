import time
import os, subprocess
import tempfile

from django_assets.filter import Filter


__all__ = ('SassFilter', 'SCSSFilter')


class SassFilter(Filter):
    """Converts `Sass <http://sass-lang.com/>`_ markup to real CSS.
    """

    name = 'sass'

    def __init__(self, scss=False):
        self.binary = self.get_config('SASS_BIN', what='less binary',
                                      require=False)
        self.use_scss = scss

    def input(self, _in, out, source_path, output_path):
        args = [self.binary or 'sass', '--stdin', '--style', 'expanded',
                '--debug-info', '--no-cache', '--line-comments']
        if self.use_scss:
            args.append('--scss')
        proc = subprocess.Popen(args,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                # shell: necessary on windows to execute
                                # ruby files, but doesn't work on linux.
                                shell=(os.name == 'nt'))
        stdout, stderr = proc.communicate(_in.read())

        if stderr or proc.returncode != 0:
            raise Exception(('sass: subprocess had error: stderr=%s, '+
                            'stdout=%s, returncode=%s') % (
                                            stderr, stdout, proc.returncode))

        out.write(stdout)


class SCSSFilter(SassFilter):
    """Version of the ``sass`` filter that uses the SCSS syntax.
    """

    name = 'scss'

    def __init__(self):
        super(SCSSFilter, self).__init__(scss=True)