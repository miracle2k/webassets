import subprocess

from webassets.filter import Filter, FilterError, option


__all__ = ('Stylus',)


class Stylus(Filter):
    """Converts `Stylus <http://learnboost.github.com/stylus/>`_ markup to CSS.

    Requires the Stylus executable to be available externally. You can install
    it using the `Node Package Manager <http://npmjs.org/>`_::

        $ npm install stylus

    Supported configuration options:

    STYLUS_BIN
        The path to the Stylus binary. If not set, assumes ``stylus`` is in the
        system path.

    STYLUS_PLUGINS
        A Python list of Stylus plugins to use. Each plugin will be included
        via Stylus's command-line ``--use`` argument.

    STYLUS_EXTRA_ARGS
        A Python list of any additional command-line arguments.
    """

    name = 'stylus'
    options = {
        'stylus': 'STYLUS_BIN',
        'plugins': option('STYLUS_PLUGINS', type=list),
        'extra_args': option('STYLUS_EXTRA_ARGS', type=list),
    }
    max_debug_level = True

    def input(self, _in, out, **kwargs):
        args = [self.stylus or 'stylus']
        for plugin in self.plugins or []:
            args.extend(('--use', plugin))
        if self.extra_args:
            args.extend(self.extra_args)

        PIPE = subprocess.PIPE
        proc = subprocess.Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate(_in.read())

        if proc.returncode != 0:
            raise FilterError('%s: subprocess had error: stderr=%s, code=%s',
                              self.name, stderr, proc.returncode)
        out.write(stdout)
