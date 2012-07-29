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
    parsed = urlparse.urlsplit(s)
    return bool(parsed.scheme and parsed.netloc) and len(parsed.scheme) > 1


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

    def _get_contents(self):
        return self._contents
    def _set_contents(self, value):
        self._contents = value
        self._resolved_contents = None
    contents = property(_get_contents, _set_contents)

    def resolve_contents(self, env=None, force=False):
        """Return an actual list of source files.

        What the user specifies as the bundle contents cannot be
        processed directly. There may be glob patterns of course. We
        may need to search the load path. It's common for third party
        extensions to provide support for referencing assets spread
        across multiple directories.

        This passes everything through :class:`Environment.resolver`,
        through which this process can be customized.

        At this point, we also validate source paths to complain about
        missing files early.

        The return value is a list of 2-tuples ``(original_item,
        abspath)``. In the case of urls and nested bundles both tuple
        values are the same.

        Set ``force`` to ignore any cache, and always re-resolve
        glob  patterns.
        """
        env = self._get_env(env)

        # TODO: We cache the values, which in theory is problematic, since
        # due to changes in the env object, the result of the globbing may
        # change. Not to mention that a different env object may be passed
        # in. We should find a fix for this.
        if getattr(self, '_resolved_contents', None) is None or force:
            resolved = []
            for item in self.contents:
                try:
                    result = env.resolver.resolve_source(item)
                except IOError, e:
                    raise ContainerError(e)
                if not isinstance(result, list):
                    result = [result]

                # Exclude the output file.
                # TODO: This will not work for nested bundle contents. If it
                # doesn't work properly anyway, should be do it in the first
                # place? If there are multiple versions, it will fail as well.
                # TODO: There is also the question whether we can/should
                # exclude glob duplicates.
                if self.output:
                    try:
                        result.remove(self.resolve_output(env))
                    except (ValueError, ContainerError):
                        pass

                resolved.extend(map(lambda r: (item, r), result))

            self._resolved_contents = resolved
        return self._resolved_contents
