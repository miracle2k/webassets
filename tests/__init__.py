def setup():
    # For some strange reason (using Python 2.6.6), if a warning has
    # already been raised somewhere else before a test attempts to
    # capture and verify it using warnings.catch_warnings(), the warning
    # will not be re-raised again, regardless of any calls to
    # warnings.simplefilter() or warnings.resetwarnings(). It is as if
    # once a warning is on some internal "do not duplicate" list, it can't
    # be removed from there.
    #
    # By having the "always" filter installed before anything else, we
    # ensure every test can rely on being able to capture all warnings.
    import warnings
    warnings.resetwarnings()
    warnings.simplefilter("always")
