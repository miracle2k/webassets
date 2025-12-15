from webassets.filter import Filter


__all__ = ('Slimit',)


class Slimit(Filter):
    """Minifies JS.

    Requires the ``slimit3k`` package (https://github.com/tetframework/slimit3k),
    which is a JavaScript minifier written in Python. It compiles JavaScript
    into more compact code so that it downloads and runs faster.

    It offers mangle and mangle_toplevel options through SLIMIT_MANGLE and SLIMIT_MANGLE_TOPLEVEL

    Note that ``slimit3k`` is a fork of the original, but no longer unmaintained
    ``slimit`` package (https://github.com/rspivak/slimit) which no longer
    builds on Python 3.14.
    """

    name = 'slimit'
    options = {"mangle": "SLIMIT_MANGLE", "mangle_toplevel": "SLIMIT_MANGLE_TOPLEVEL"}

    def setup(self):
        try:
            import slimit
        except ImportError:
            raise EnvironmentError('The "slimit" package is not installed.')
        else:
            self.slimit = slimit

    def output(self, _in, out, **kw):
        out.write(self.slimit.minify(_in.read(),
                mangle=self.mangle, mangle_toplevel=self.mangle_toplevel))
