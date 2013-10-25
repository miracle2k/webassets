from __future__ import with_statement
import re

from webassets.test import TempDirHelper, TempEnvironmentHelper


__all__ = ('TempDirHelper', 'TempEnvironmentHelper', 'noop',
           'assert_raises_regexp', 'check_warnings')


# Define a noop filter; occasionally in tests we need to define
# a filter to be able to test a certain piece of functionality,.
noop = lambda _in, out: out.write(_in.read())


try:
    # Python 3
    from nose.tools import assert_raises_regex
except ImportError:
    try:
        # Python >= 2.7
        from nose.tools import assert_raises_regexp as assert_raises_regex
    except:
        # Python < 2.7
        def assert_raises_regex(expected, regexp, callable, *a, **kw):
            try:
                callable(*a, **kw)
            except expected as e:
                if isinstance(regexp, basestring):
                    regexp = re.compile(regexp)
                if not regexp.search(str(e.message)):
                    raise self.failureException('"%s" does not match "%s"' %
                             (regexp.pattern, str(e.message)))
            else:
                if hasattr(expected,'__name__'): excName = expected.__name__
                else: excName = str(expected)
                raise AssertionError("%s not raised" % excName)


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
