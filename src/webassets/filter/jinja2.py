from __future__ import absolute_import
from webassets.filter import Filter


__all__ = ('Jinja2',)


class Jinja2(Filter):
    """Process a file through the Jinja2 templating engine.

    Requires the ``jinja2`` package (https://github.com/mitsuhiko/jinja2).

    The Jinja2 context can be specified with the `JINJA2_CONTEXT` configuration
    option or directly with `context={...}`. Example:

    .. code-block:: python

        Bundle('input.css', filters=Jinja2(context={'foo': 'bar'}))
    """

    name = 'jinja2'
    max_debug_level = None
    options = {
        'context': 'JINJA2_CONTEXT',
    }

    def setup(self):
        try:
            import jinja2
        except ImportError:
            raise EnvironmentError('The "jinja2" package is not installed.')
        else:
            self.jinja2 = jinja2
        super(Jinja2, self).setup()

    def input(self, _in, out, **kw):
        out.write(self.jinja2.Template(_in.read()).render(self.context or {}))
