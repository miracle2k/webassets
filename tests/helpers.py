import re

from webassets.test import TempDirHelper, TempEnvironmentHelper


__all__ = ('TempDirHelper', 'TempEnvironmentHelper', 'noop',
           'assert_raises_regexp')


# Define a noop filter; occasionally in tests we need to define
# a filter to be able to test a certain piece of functionality,.
noop = lambda _in, out: out.write(_in.read())


try:
    from nose.tools import assert_raises_regexp
except ImportError:
    # Python < 2.7
    def assert_raises_regexp(expected, regexp, callable, *a, **kw):
        try:
            callable(*a, **kw)
        except expected, e:
            if isinstance(regexp, basestring):
                regexp = re.compile(regexp)
            if not regexp.search(str(e.message)):
                raise self.failureException('"%s" does not match "%s"' %
                         (regexp.pattern, str(e.message)))
        else:
            if hasattr(expected,'__name__'): excName = expected.__name__
            else: excName = str(expected)
            raise AssertionError, "%s not raised" % excName
