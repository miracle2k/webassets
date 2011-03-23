import time
import os, subprocess
import tempfile

from webassets.filter import Filter


__all__ = ('SassFilter', 'SCSSFilter')


class SassFilter(Filter):
    """Converts `Sass <http://sass-lang.com/>`_ markup to real CSS.
    """

    name = 'sass'

    def __init__(self, scss=False, debug_info=None):
        super(SassFilter, self).__init__()
        self.use_scss = scss
        self.debug_info = debug_info

    def setup(self):
        self.binary = self.get_config('SASS_BIN', what='sass binary',
                                      require=False)
        if self.debug_info is None:
            self.debug_info = self.get_config('SASS_DEBUG_INFO', require=False)

    def input(self, _in, out, source_path, output_path):
        old_dir = os.getcwd()
        os.chdir(os.path.dirname(source_path))
        try:
            args = [self.binary or 'sass', '--stdin', '--style', 'expanded',
                    '--no-cache', '--line-comments']
            if not self.debug_info is False:
                args.append('--debug-info')
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

            if proc.returncode != 0:
                raise Exception(('sass: subprocess had error: stderr=%s, '+
                                'stdout=%s, returncode=%s') % (
                                                stderr, stdout, proc.returncode))
            elif stderr:
                print "sass filter has warnings:", stderr

            out.write(stdout)
        finally:
            os.chdir(old_dir)


class SCSSFilter(SassFilter):
    """Version of the ``sass`` filter that uses the SCSS syntax.
    """

    name = 'scss'

    def __init__(self, *a, **kw):
        assert not 'scss' in kw
        kw['scss'] = True
        super(SCSSFilter, self).__init__(*a, **kw)
