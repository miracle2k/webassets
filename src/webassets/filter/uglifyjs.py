from webassets.filter import ExternalTool


__all__ = ('UglifyJS',)


class UglifyJS(ExternalTool):
    """
    Minify Javascript using `UglifyJS <https://github.com/mishoo/UglifyJS/>`_.

    UglifyJS is an external tool written for NodeJS; this filter assumes that
    the ``uglifyjs`` executable is in the path. Otherwise, you may define
    a ``UGLIFYJS_BIN`` setting.

    Additional options may be passed to ``uglifyjs`` using the setting
    ``UGLIFYJS_EXTRA_ARGS``, which expects a list of strings.
    """

    name = 'uglifyjs'
    options = {
        'binary': 'UGLIFYJS_BIN',
        'extra_args': 'UGLIFYJS_EXTRA_ARGS',
    }

    def output(self, _in, out, **kw):
        args = [self.binary or 'uglifyjs']
        if self.extra_args:
            args.extend(self.extra_args)
        self.subprocess(args, out, _in)
