import re

from webassets.test import TempDirHelper, TempEnvironmentHelper


__all__ = ('TempDirHelper', 'TempEnvironmentHelper', 'noop',
           'assert_raises_regex', 'check_warnings')


# Define a noop filter; occasionally in tests we need to define
# a filter to be able to test a certain piece of functionality,.
noop = lambda _in, out: out.write(_in.read())


from pytest import raises
def assert_raises_regex(expected, regexp, callable, *a, **kw):
    raises(expected, callable, *a, **kw).match(regexp)


try:
    from test.support import check_warnings  # Python 3
except ImportError:

    try:
        from test.test_support import check_warnings   # Python 2
    except ImportError:
        # Python < 2.6
        import contextlib

        @contextlib.contextmanager
        def check_warnings(*filters, **kwargs):
            # We cannot reasonably support this, we'd have to copy to much code.
            # (or write our own). Since this is only testing warnings output,
            # we might slide by ignoring it.
            yield
