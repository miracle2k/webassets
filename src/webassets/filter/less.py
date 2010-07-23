import time
import os, subprocess
import tempfile

from webassets.filter import Filter


__all__ = ('LessFilter',)


class LessFilter(Filter):
    """Converts `Less <http://lesscss.org/>`_ markup to real CSS.

    If you want to combine it with other CSS filters, make sure this
    one runs first.

    **Note**: Currently, this needs to be the very first filter
    applied. Changes by filters that ran before will be lost.
    """
    """XXX: This currently needs to be the very first filter applied. This is
    because it uses the "source filter" mechanism to support "@includes"
    in less, i.e. it let's the less compiler work directly with the source
    file, and ignores the input stream. Filters previously already applied
    will be lost. Ways to solve this:
        - Let filters specify that they need to be first (and auto do so,
          or raise an exception).
        - Rewrite the less filter:
             - It could properly use the input stream, and just create the
               temp file in the same directory as the input path.
             - It could rewrite @includes via regex, as the cssrewrite filter
               does, before passing the tempfile on to lessc.

    XXX: Depending on how less is actually used in practice, it might actually
    be a valid use case to NOT have this be a source filter, so that one can
    split the css files into various less files, referencing variables in other
    files' - without using @include, instead having them merged together by
    django-assets. This will currently not work because we compile each
    file separately, and the compiler would fail at undefined variables.
    """

    name = 'less'

    def setup(self):
        self.less = self.get_config('LESS_PATH', what='less binary')

    def input(self, _in, out, source_path, output_path):
        """Less currently doesn't take data from stdin, and doesn't allow
        us from stdout either. Neither does it return a proper non-0 error
        code when an error occurs, or even write to stderr (stdout instead)!

        Hopefully this will improve in the future:

        http://groups.google.com/group/lesscss/browse_thread/thread/3aed033a44c51b4c/b713148afde87e81
        """
        # TODO: Use NamedTemporaryFile.
        outtemp_name = os.path.join(tempfile.gettempdir(),
                                    'assets_temp_%d.css' % int(time.time()))

        proc = subprocess.Popen([self.less, source_path, outtemp_name],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                # shell: necessary on windows to execute
                                # ruby files, but doesn't work on linux.
                                shell=(os.name == 'nt'))
        stdout, stderr = proc.communicate()

        # less only writes to stdout, as noted in the method doc, but
        # check everything anyway.
        if stdout or stderr or proc.returncode != 0:
            if os.path.exists(outtemp_name):
                os.unlink(outtemp_name)
            raise Exception(('less: subprocess had error: stderr=%s, '+
                            'stdout=%s, returncode=%s') % (
                                            stderr, stdout, proc.returncode))

        outtemp = open(outtemp_name)
        try:
            out.write(outtemp.read())
        finally:
            outtemp.close()

            os.unlink(outtemp_name)