import os
import subprocess

from webassets.exceptions import FilterError

from .sass import Sass


__all__ = ('NodeSass', )


class NodeSass(Sass):
    name = 'node-sass'
    options = {
        'binary': 'SASS_BIN',
        'debug_info': 'SASS_DEBUG_INFO',
        'use_scss': ('scss', 'SASS_USE_SCSS'),
        'as_output': 'SASS_AS_OUTPUT',
        'load_paths': 'SASS_LOAD_PATHS',
        'style': 'SASS_STYLE',
    }
    max_debug_level = None

    def _apply_sass(self, _in, out, cd=None):
        # Switch to source file directory if asked, so that this directory
        # is by default on the load path. We could pass it via --include-paths, but then
        # files in the (undefined) wd could shadow the correct files.
        old_dir = os.getcwd()
        if cd:
            os.chdir(cd)

        try:
            args = [self.binary or 'node-sass',
                    '--output-style', self.style or 'expanded']

            if not self.use_scss:
                args.append("--indented-syntax")

            if (self.ctx.environment.debug if self.debug_info is None else self.debug_info):
                args.append('--debug-info')
            for path in self.load_paths or []:
                args.extend(['--include-path', path])

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
                print("node-sass filter has warnings:", stderr)

            out.write(stdout.decode('utf-8'))
        finally:
            if cd:
                os.chdir(old_dir)
