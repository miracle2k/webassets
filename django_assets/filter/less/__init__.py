"""Converts `Less <http://lesscss.org/>`_ markup to real CSS.

If you want to combine it with other CSS filters, make sure this one runs
first.
"""


import time
import os, subprocess
import tempfile
from django_assets.conf import settings

def _get_less_path():
    path = getattr(settings, 'LESS_PATH', None)
    if not path:
        path = os.environ.get('LESS_PATH')
        if not path:
            raise EnvironmentError('less binary was not found on '
                'your system. Define a LESS_PATH setting or '
                'environment variable.')
    return path

# fail early
less = _get_less_path()

def apply(_in, out):
    """Less currently doesn't take data from stdin, and doesn't allow
  	us from stdout either. Neither does it return a proper non-0 error
  	code when an error occurs, or even write to stderr (stdout instead)!

  	Hopefully this will improve in the future:

  	http://groups.google.com/group/lesscss/browse_thread/thread/3aed033a44c51b4c/b713148afde87e81
  	"""
    intemp = tempfile.NamedTemporaryFile()
    try:
        outtemp_name = os.path.join(tempfile.gettempdir(),
                                    'assets_temp_%d.css' % int(time.time()))
    	intemp.write(_in.read())

    	proc = subprocess.Popen([less, intemp.name, outtemp_name],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
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
    finally:
    	intemp.close()