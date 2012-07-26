import urlparse
import os
from exceptions import ContainerError

try:
    # Current version of glob2 does not let us access has_magic :/
    import glob2 as glob
    from glob import has_magic
except ImportError:
    import glob
    from glob import has_magic

def is_url(s):
    if not isinstance(s, str):
        return False
    scheme = urlparse.urlsplit(s).scheme
    return bool(scheme) and len(scheme) > 1

class Container(object):

    def __init__(self):
        pass

    def _get_contents(self):
        return self._contents
    def _set_contents(self, value):
        self._contents = value
        self._resolved_contents = None
    contents = property(_get_contents, _set_contents)

    def _get_env(self, env):
        # Note how bool(env) can be False, due to __len__.
        env = env if env is not None else self.env
        if env is None:
            raise ContainerError('Container not connected to an environment')
        return env

    def resolve_contents(self, env=None, force=False):
        """Convert bundle contents into something that can be easily processed.

        - Glob patterns are resolved
        - Validate all the source paths to complain about missing files early.
        - Third party extensions get to hook into this to provide a basic
          virtualized filesystem.

        The return value is a list of 2-tuples (relpath, abspath). The first
        element is the path that is assumed to be relative to the
        ``Environment.directory`` value. We need it to construct urls to the
        source files.
        The second element is the absolute path to the actual location of the
        file. Depending on the magic a third party extension does, this may be
        somewhere completely different.

        URLs and nested Bundles are returned as a 2-tuple where both items are
        the same.

        Set ``force`` to ignore any cache, and always re-resolve glob patterns.
        """
        env = self._get_env(env)

        # TODO: We cache the values, which in theory is problematic, since
        # due to changes in the env object, the result of the globbing may
        # change. Not to mention that a different env object may be passed
        # in. We should find a fix for this.
        if getattr(self, '_resolved_contents', None) is None or force:
            l = []
            for item in self.contents:
                if isinstance(item, Container):
                    l.append((item, item))
                else:
                    if is_url(item):
                        # Is a URL
                        l.append((item, item))
                    elif isinstance(item, basestring) and has_magic(item):
                        # Is globbed pattern
                        path = env.abspath(item)
                        for f in glob.glob(path):
                            if os.path.isdir(f):
                                continue
                            if self.output and env.abspath(self.output) == f:
                                # Exclude the output file. Note this will
                                # not work if nested bundles do the
                                # including. TODO: Should be even have this
                                # test if it doesn't work properly? Should
                                # be throw an error during building instead?
                                # Or can be give this method access to the
                                # parent bundle, since allowing env settings
                                # overrides in bundles is planned anyway?
                                continue
                            l.append((f[len(path)-len(item):], f))
                    else:
                        # Is just a normal path; Send it through
                        # _normalize_source_path().
                        try:
                            l.append((item, env._normalize_source_path(item)))
                        except IOError, e:
                            raise BundleError(e)
            self._resolved_contents = l
        return self._resolved_contents
