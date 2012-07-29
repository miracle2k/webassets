from __future__ import with_statement

from webassets.filter import ExternalTool
from webassets.utils import working_directory


class Less(ExternalTool):
    """Converts `less <http://lesscss.org/>`_ markup to real CSS.

    This depends on the NodeJS implementation of less, installable via npm.
    To use the old Ruby-based version (implemented in the 1.x Ruby gem), see
    :class:`~.less_ruby.Less`.

    *Supported configuration options*:

    LESS_BIN (binary)
        Path to the less executable used to compile source files. By default,
        the filter will attempt to run ``lessc`` via the system path.

    LESS_RUN_IN_DEBUG (run_in_debug)
        By default, the filter will compile in debug mode. Since the less
        compiler is written in Javascript and capable of running in the
        browser, you can set this to ``False`` to have your original less
        source files served (see below).

    .. admonition:: Compiling less in the browser

        less is an interesting case because it is written in Javascript and
        capable of running in the browser. While for performance reason you
        should prebuild your stylesheets in production, while developing you
        may be interested in serving the original less files to the client,
        and have less compile them in the browser.

        To do so, you first need to make sure the less filter is not applied
        when :attr:`Environment.debug` is ``True``. You can do so via an
        option::

            env.config['less_run_in_debug'] = False

        Second, in order for the less to identify the  less source files as
        needing to be compiled, they have to be referenced with a
        ``rel="stylesheet/less"`` attribute. One way to do this is to use the
        :attr:`Bundle.extra` dictionary, which works well with the template
        tags that webassets provides for some template languages::

            less_bundle = Bundle(
                '**/*.less',
                filters='less',
                extra={'rel': 'stylesheet/less' if env.debug else 'stylesheet'}
            )

        Then, for example in a Jinja2 template, you would write::

            {% assets less_bundle %}
                <link rel="{{ EXTRA.rel }}" type="text/css" href="{{ ASSET_URL }}">
            {% endassets %}

        With this, the ``<link>`` tag will sport the correct ``rel`` value both
        in development and in production.

        Finally, you need to include the less compiler::

            if env.debug:
                js_bundle.contents += 'http://lesscss.googlecode.com/files/less-1.3.0.min.js'
    """

    name = 'less'
    options = {
        'less': ('binary', 'LESS_BIN'),
        'run_in_debug': 'LESS_RUN_IN_DEBUG',
    }
    max_debug_level = None

    def setup(self):
        super(Less, self).setup()
        if self.run_in_debug is False:
            # Disable running in debug mode for this instance.
            self.max_debug_level = False

    def input(self, in_, out, source_path, **kw):
        # Set working directory to the source file so that includes are found
        with working_directory(filename=source_path):
            self.subprocess([self.less or 'lessc', '-'], out, in_)
