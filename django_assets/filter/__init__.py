"""Assets can be filtered through one or multiple filters, modifying their
contents (think minification, compression).
"""

import cStringIO as StringIO

def get_filter(name):
    try:
        module = __import__('djutils.features.assets.filter.%s' % name, {}, {}, [''])
    except ImportError:
        raise ValueError('Filter "%s" is not valid' % name)
    return module