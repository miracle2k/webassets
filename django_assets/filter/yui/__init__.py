"""Minify Javascript and CSS with
`YUI Compressor <http://developer.yahoo.com/yui/compressor/>`_.

YUI Compressor is an external tool written in Java, which needs to be
available. You can define a ``YUI_COMPRESSOR_PATH`` setting that
points to the ``.jar`` file. Otherwise, an environment variable by
the same name is tried. The filter will also look for a ``JAVA_HOME``
environment variable to run the ``.jar`` file, or will otherwise
assume that ``java`` is on the system path.
"""

import os, subprocess

from django_assets.filter import Filter


__all__ = ('YUIJSFilter', 'YUICSSFilter',)


class YUIBase(Filter):

    # Will cause this base class no not be loaded.
    name = None

    def setup(self):
        self.yui = self.get_config('YUI_COMPRESSOR_PATH',
                                   what='YUI Compressor')

        # We can reasonably expect that java is just on the path, so
        # don't require it, but hope for the best.
        self.java = self.get_config(env=JAVA_HOME, require=False)
        if self.java is not None:
            self.java = os.path.join(path, 'bin/java')
        else:
            self.java = 'java'

    def apply(self, _in, out):
        proc = subprocess.Popen(
            [self.java, '-jar', self.yui, '--type=%s' % self.mode],
            # we cannot use the in/out streams directly, as they might be
            # StringIO objects (which are not supported by subprocess)
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(_in.read())
        if proc.returncode:
            raise Exception('yui compressor: subprocess returned a '
                'non-success result code: %s' % proc.returncode)
            # stderr contains error messages
        else:
            out.write(stdout)


class YUIJSFilter(YUIBase):
    name = 'yui_js'
    mode = 'js'


class YUICSSFilter(YUIBase):
    name = 'yui_css'
    mode = 'css'