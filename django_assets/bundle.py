__all__ = ('Bundle',)


class Bundle(object):
    """A bundle is the unit django-assets uses to organize groups of media
    files, which filters to apply and where to store them.

    Bundles can be nested.
    """

    def __init__(self, *contents, **options):
        self.contents = contents
        self.output = options.get('output')
        self.filters = options.get('filters')
        self.extra_data = {}


    def __repr__(self):
        return "<Bundle output=%s, filters=%s, contents=%s>" % (
            self.output,
            self.filters,
            self.contents,
        )