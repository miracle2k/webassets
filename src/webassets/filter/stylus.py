from webassets.filter import ExternalTool, option


__all__ = ('Stylus',)


class Stylus(ExternalTool):
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
    max_debug_level = None

    def input(self, _in, out, **kwargs):
        args = [self.stylus or 'stylus']
        for plugin in self.plugins or []:
            args.extend(('--use', plugin))
        if self.extra_args:
            args.extend(self.extra_args)
        self.subprocess(args, out, _in)
