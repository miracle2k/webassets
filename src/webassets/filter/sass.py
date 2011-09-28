import os, subprocess

from webassets.filter import Filter
from webassets.exceptions import FilterError


__all__ = ('SassFilter', 'SCSSFilter')


class SassFilter(Filter):
    """Converts `Sass <http://sass-lang.com/>`_ markup to real CSS.
    """

    name = 'sass'

    def __init__(self, scss=False, debug_info=None, as_output=False,
                 includes_dir=None):
        super(SassFilter, self).__init__()
        self.use_scss = scss
        self.debug_info = debug_info
        self.as_output = as_output
        self.includes_dir = includes_dir

    def setup(self):
        self.binary = self.get_config('SASS_BIN', what='sass binary',
                                      require=False)
        if self.debug_info is None:
            self.debug_info = self.get_config('SASS_DEBUG_INFO', require=False)

    def _apply_sass(self, _in, out, includes_path):
        if includes_path:
            old_dir = os.getcwd()
            os.chdir(includes_path)

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
                raise FilterError(('sass: subprocess had error: stderr=%s, '+
                                   'stdout=%s, returncode=%s') % (
                                                stderr, stdout, proc.returncode))
            elif stderr:
                print "sass filter has warnings:", stderr

            out.write(stdout)
        finally:
            if includes_path:
                os.chdir(old_dir)

    def input(self, _in, out, source_path, output_path):
        if self.as_output:
            out.write(_in.read())
        else:
            self._apply_sass(
                _in, out, self.includes_dir or os.path.dirname(source_path))

    def output(self, _in, out, **kwargs):
        if not self.as_output:
            out.write(_in.read())
        else:
            self._apply_sass(_in, out, self.includes_dir)


class SCSSFilter(SassFilter):
    """Version of the ``sass`` filter that uses the SCSS syntax.
    """

    name = 'scss'

    def __init__(self, *a, **kw):
        assert not 'scss' in kw
        kw['scss'] = True
        super(SCSSFilter, self).__init__(*a, **kw)
