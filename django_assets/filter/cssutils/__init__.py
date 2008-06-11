"""Minifies CSS by removing whitespace, comments etc.

Based on the cssutils library from:
    http://cthedot.de/cssutils/

Like csstidy, it works as a parser on the syntax level, so
invalid CSS input can potentially result in data loss.
"""

import cssutils
import logging
import logging.handlers
from django.conf import settings

# cssutils logs to stdout by default, hide that in production
if not settings.DEBUG:
    log = logging.getLogger('assets.cssutils')
    log.addHandler(logging.handlers.MemoryHandler(10))
    cssutils.log.setlog(log)

def apply(_in, out):
    sheet = cssutils.parseString(_in.read())
    cssutils.ser.prefs.useMinified()
    out.write(sheet.cssText)