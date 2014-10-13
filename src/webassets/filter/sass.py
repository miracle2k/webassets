from __future__ import print_function
import os, subprocess

from webassets.filter import Filter
from webassets.exceptions import FilterError, ImminentDeprecationWarning
from webassets.cache import FilesystemCache


__all__ = ('Sass', 'SCSS')


class Sass(Filter):
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
    the ``load_paths`` argument, which specifies the path to which
    the imports are relative to (this is implemented by changing the
    working directory before calling the ``sass`` executable)::

        sass = get_filter('sass', as_output=True, load_paths='/tmp')

    If you are confused as to why this is necessary, consider that
    in the case of an output filter, the source files might come from
    various places in the filesystem, put are merged together and
    passed to Sass as one big chunk. The filter cannot by itself know
    which of the source directories to use as a base.

    Support configuration options:

    SASS_BIN
        The path to the Sass binary. If not set, the filter will
        try to run ``sass`` as if it's in the system path.

    SASS_STYLE
        The style for the output CSS. Can be one of ``expanded`` (default),
        ``nested``, ``compact`` or ``compressed``.

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
    options = {
        'binary': 'SASS_BIN',
        'use_scss': ('scss', 'SASS_USE_SCSS'),
        'use_compass': ('use_compass', 'SASS_COMPASS'),
        'debug_info': 'SASS_DEBUG_INFO',
        'as_output': 'SASS_AS_OUTPUT',
        'load_paths': 'SASS_LOAD_PATHS',
        'libs': 'SASS_LIBS',
        'style': 'SASS_STYLE',
    }
    max_debug_level = None

    def _apply_sass(self, _in, out, cd=None):
        # Switch to source file directory if asked, so that this directory
        # is by default on the load path. We could pass it via -I, but then
        # files in the (undefined) wd could shadow the correct files.
        old_dir = os.getcwd()
        if cd:
            os.chdir(cd)

        try:
            args = [self.binary or 'sass',
                    '--stdin',
                    '--style', self.style or 'expanded',
                    '--line-comments']
            if isinstance(self.ctx.cache, FilesystemCache):
                args.extend(['--cache-location',
                             os.path.join(old_dir, self.ctx.cache.directory, 'sass')])
            elif not cd:
                # Without a fixed working directory, the location of the cache
                # is basically undefined, so prefer not to use one at all.
                args.extend(['--no-cache'])
            if (self.ctx.environment.debug if self.debug_info is None else self.debug_info):
                args.append('--debug-info')
            if self.use_scss:
                args.append('--scss')
            if self.use_compass:
                args.append('--compass')
            for path in self.load_paths or []:
                args.extend(['-I', path])
            for lib in self.libs or []:
                args.extend(['-r', lib])

            proc = subprocess.Popen(args,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    # shell: necessary on windows to execute
                                    # ruby files, but doesn't work on linux.
                                    shell=(os.name == 'nt'))
            stdout, stderr = proc.communicate(_in.read().encode('utf-8'))

            if proc.returncode != 0:
                raise FilterError(('sass: subprocess had error: stderr=%s, '+
                                   'stdout=%s, returncode=%s') % (
                                                stderr, stdout, proc.returncode))
            elif stderr:
                print("sass filter has warnings:", stderr)

            out.write(stdout.decode('utf-8'))
        finally:
            if cd:
                os.chdir(old_dir)

    def input(self, _in, out, source_path, output_path, **kw):
        if self.as_output:
            out.write(_in.read())
        else:
            self._apply_sass(_in, out, os.path.dirname(source_path))

    def output(self, _in, out, **kwargs):
        if not self.as_output:
            out.write(_in.read())
        else:
            self._apply_sass(_in, out)


class SCSS(Sass):
    """Version of the ``sass`` filter that uses the SCSS syntax.
    """

    name = 'scss'

    def __init__(self, *a, **kw):
        assert not 'scss' in kw
        kw['scss'] = True
        super(SCSS, self).__init__(*a, **kw)
