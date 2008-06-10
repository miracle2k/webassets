"""Minify Javascript and CSS with YUI Compressor. This filter defaults to
JS mode, but it is recommended that you use the 'yui_js' and 'yui_css'
filters instead.

YUI Compressor is an external tool, which needs to be available (also, java
is required).

You can define a YUI_COMPRESSOR_PATH setting that points to the .jar file.
Otherwise, we will attempt to find the path via an environment variable by
the same name. The filter will also look for a JAVA_HOME environment
variable to run the .jar file, or will otherwise assume that "java" is
on the system path.

For more information, see:
    http://developer.yahoo.com/yui/compressor/
"""

import os, subprocess
from django_assets.conf import settings

def _get_yui_path():
    path = getattr(settings, 'YUI_COMPRESSOR_PATH', None)
    if not path:
        path = os.environ.get('YUI_COMPRESSOR_PATH')
        if not path:
            raise EnvironmentError('YUI Compressor was not found on '
                'your system. Define a YUI_COMPRESSOR_PATH setting or '
                'environment variable.')
    return path

def _get_java_path():
    path = os.environ.get('JAVA_HOME')
    if path:
        return os.path.join(path, 'bin/java')
    else:
        return 'java'

# fail early
yui = _get_yui_path()

def apply(_in, out, mode='js'):
    java = _get_java_path()
    proc = subprocess.Popen(
        [java, '-jar', yui, '--type=%s'%mode],
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