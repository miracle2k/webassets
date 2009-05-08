"""Minifies CSS by removing whitespace, comments etc., using the Python 
`cssutils <http://cthedot.de/cssutils/>`_ library.

Note that since this works as a parser on the syntax level, so invalid CSS 
input could potentially result in data loss.
"""

import cssutils
import logging
import logging.handlers
from django.conf import settings

try:
    # cssutils logs to stdout by default, hide that in production
    if not settings.DEBUG:
        log = logging.getLogger('assets.cssutils')
        log.addHandler(logging.handlers.MemoryHandler(10))
        cssutils.log.setlog(log)
except ImportError:
    # During doc generation, Django is not going to be setup and will 
    # fail when the settings object is accessed. That's ok though.
    pass

def apply(_in, out):
    sheet = cssutils.parseString(_in.read())
    cssutils.ser.prefs.useMinified()
    out.write(sheet.cssText)