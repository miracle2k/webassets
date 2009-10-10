__all__ = ('Bundle',)


class Bundle(object):
    """A bundle is the unit django-assets uses to organize groups of media
    files, which filters to apply and where to store them.

    Bundles can be nested.
    """

    def __init__(output=None, filters=None, *contents):
        self.contents = contents
        self.output = output
        self.filters = filters
        self.extra_data = {}