"""Minify Javascript with `Google Closure Compiler
<https://code.google.com/p/closure-compiler/>`_.

Google Closure Compiler is an external tool written in Java, which needs
to be available. You can define a ``CLOSURE_COMPRESSOR_PATH`` setting that
points to the ``.jar`` file. Otherwise, an environment variable by
the same name is tried. The filter will also look for a ``JAVA_HOME``
environment variable to run the ``.jar`` file, or will otherwise
assume that ``java`` is on the system path.

There is also a ``CLOSURE_COMPRESSOR_OPTIMIZATION`` option, which corresponds
to Google Closure's `compilation level parameter
<https://code.google.com/closure/compiler/docs/compilation_levels.html>`_.
"""

from webassets.filter import Filter, JavaMixin


__all__ = ('ClosureJSFilter',)


class ClosureJSFilter(Filter, JavaMixin):

    name = 'closure_js'
    mode = 'js'

    def setup(self):
        self.jar = self.get_config('CLOSURE_COMPRESSOR_PATH',
                                   what='Google Closure Compiler')
        self.opt = self.get_config('CLOSURE_COMPRESSOR_OPTIMIZATION',
                                   require=False,
                                   what='Google Closure optimization level')
        if not self.opt:
            self.opt = 'WHITESPACE_ONLY'
        self.java_setup()

    def output(self, _in, out, **kw):
        self.java_run(_in, out, ['--charset', 'UTF-8',
                                 '--compilation_level', self.opt])
