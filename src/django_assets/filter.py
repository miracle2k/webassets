"""Django specific filters.

For those to be registered automatically, make sure the main
django_assets namespace imports this file.
"""


from webassets.filter import Filter


class I18nFilter(Filter):
    """Will insert the contents of all
    ``django.views.i18n.javascript_catalog()`` views installed
    in ROOT_URLCONF at the top of the output, in all available
    languages.

    TODO: A filter should be able to suggested dependencies to
    the build process (or have it's own), so that an automatic
    rebuild can happen if the locales change (which currently
    it would not).

    When using multiple catalog views, the helper function
    Django inserts (interpolate etc.) will exist multiple times,
    but one of the smarter Javascript compressor will be able to
    de-duplicate.
    """

    name = 'i18n'

    def output(self, _in, out):
        #
        out.write(_in.read())


