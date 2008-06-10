"""Assets can be filtered through one or multiple filters, modifying their
contents (think minification, compression).
"""

def get_filter(name):
    try:
        module = __import__('django_assets.filter.%s' % name, {}, {}, [''])
    except ImportError:
        raise ValueError('Filter "%s" is not valid' % name)
    return module