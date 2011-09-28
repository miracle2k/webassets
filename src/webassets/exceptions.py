__all__ = ('BundleError', 'BuildError', 'FilterError',)


class BundleError(Exception):
    pass


class BuildError(BundleError):
    pass


class FilterError(BuildError):
    pass
