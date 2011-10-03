import re
from webassets import Environment, Bundle
from webassets.test import TempDirHelper


__all__ = ('TempDirHelper', 'TempEnvironmentHelper', 'noop',
           'assert_raises_regexp')


# Define a noop filter; occasionally in tests we need to define
# a filter to be able to test a certain piece of functionality,.
noop = lambda _in, out: out.write(_in.read())


class TempEnvironmentHelper(TempDirHelper):
    """Base-class for tests which provides a pre-created
    environment, based in a temporary directory, and utility
    methods to do filesystem operations within that directory.
    """

    default_files = {'in1': 'A', 'in2': 'B', 'in3': 'C', 'in4': 'D'}

    def setup(self):
        TempDirHelper.setup(self)

        self.m = Environment(self._tempdir_created, '')
        # Unless we explicitly test it, we don't want to use the cache
        # during testing.
        self.m.cache = False

    def mkbundle(self, *a, **kw):
        b = Bundle(*a, **kw)
        b.env = self.m
        return b


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
