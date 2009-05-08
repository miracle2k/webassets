"""Minify Javascript using YUI Compressor.

See the ``yui`` filter for more information.
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