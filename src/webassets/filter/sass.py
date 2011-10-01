import os, subprocess

from webassets.filter import Filter
from webassets.exceptions import FilterError
from webassets.cache import FilesystemCache


__all__ = ('SassFilter', 'SCSSFilter')


class SassFilter(Filter):
    """Converts `Sass <http://sass-lang.com/>`_ markup to real CSS.

    Requires the Sass executable to be available externally. To install
    it, you might be able to do::

         $ sudo gem install sass

    By default, this works as an "input filter", meaning ``sass`` is
    called for each source file in the bundle. This is because the
    path of the source file is required so that @import directives
    within the Sass file can be correctly resolved.

    However, it is possible to use this filter as an "output filter",
    meaning the source files will first be concatenated, and then the
    Sass filter is applied in one go. This can provide a speedup for
    bigger projects.

    To use Sass as an output filter::

        from webassets.filter import get_filter
        sass = get_filter('sass', as_output=True)
        Bundle(...., filters=(sass,))

    If you want to use the output filter mode and still also use the
    @import directive in your Sass files, you will need to pass along
    the ``includes_dir`` argument, which specifies the path to which
    the imports are relative to (this is implemented by changing the
    working directory before calling the ``sass`` executable)::

        sass = get_filter('sass', as_output=True, includes_dir='/tmp')

    If you are confused as to why this is necessary, consider that
    in the case of an output filter, the source files might come from
    various places in the filesystem, put are merged together and
    passed to Sass as one big chunk. The filter cannot by itself know
    which of the source directories to use as a base.

    Support configuration options:

    SASS_BIN
        The path to the Sass binary. If not set, the filter will
        try to run ``sass`` as if it's in the system path.

    SASS_DEBUG_INFO
        If set to ``True``, will cause Sass to output debug information
        to be used by the FireSass Firebug plugin. Corresponds to the
        ``--debug-info`` command line option of Sass.

        Note that for this, Sass uses ``@media`` rules, which are
        not removed by a CSS compressor. You will thus want to make
        sure that this option is disabled in production.

        By default, the value of this option will depend on the
        environment ``DEBUG`` setting.
    """
    # TODO: If an output filter could be passed the list of all input
    # files, the filter might be able to do something interesting with
    # it (for example, determine that all source files are in the same
    # directory).

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
                    '--line-comments']
            if isinstance(self.env.cache, FilesystemCache):
                args.extend(['--cache-location',
                             os.path.join(self.env.cache.directory, 'sass')])
            if (self.env.debug if self.debug_info is None else self.debug_info):
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
