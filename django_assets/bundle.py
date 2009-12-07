from django_assets.filter import get_filter


__all__ = ('Bundle', 'BundleError',)


class BundleError(Exception):
    pass


class Bundle(object):
    """A bundle is the unit django-assets uses to organize groups of media
    files, which filters to apply and where to store them.

    Bundles can be nested.
    """

    def __init__(self, *contents, **options):
        self.contents = contents
        self.output = options.get('output')
        self.filters = options.get('filters')
        self.debug = options.get('debug')
        self.extra_data = {}

    def __repr__(self):
        return "<Bundle output=%s, filters=%s, contents=%s>" % (
            self.output,
            self.filters,
            self.contents,
        )

    def _get_filters(self):
        return self._filters
    def _set_filters(self, value):
        """Filters may be specified in a variety of different ways,
        including by giving their name; we need to make sure we resolve
        everything to an actual filter instance.
        """
        if value is None:
            self._filters = None
            return

        if isinstance(value, basestring):
            filters = value.split(',')
        elif isinstance(value, (list, tuple)):
            filters = value
        else:
            filters = [value]
        self._filters = [get_filter(f) for f in filters]
    filters = property(_get_filters, _set_filters)