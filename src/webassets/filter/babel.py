from webassets.filter import ExternalTool

class Babel(ExternalTool):
    """Processes ES6+ code into ES5 friendly code using `Babel <https://babeljs.io/>`_.

    Requires the babel executable to be available externally.
    To install it, you might be able to do::

        $ npm install --global babel

    You probably also want some presets::

        $ npm install --global babel-preset-es2015

    Example python bundle:

    .. code-block:: python

        es2015 = get_filter('babel', presets='es2015')
        bundle = Bundle('**/*.js', filters=es2015)

    Example YAML bundle:

    .. code-block:: yaml

        es5-bundle:
            output: dist/es5.js
            config:
                BABEL_PRESETS: es2015
            filters: babel
            contents:
                - file1.js
                - file2.js

    Supported configuration options:

    BABEL_BIN
        The path to the babel binary. If not set the filter will try to run
        ``babel`` as if it's in the system path.

    BABEL_PRESETS
        Passed straight through to ``babel --presets`` to specify which babel
        presets to use
    """
    name = 'babel'
    max_debug_level = None

    options = {
        'binary': 'BABEL_BIN',
        'presets': 'BABEL_PRESETS',
    }

    def input(self, _in, out, **kw):
        args = [self.binary or 'babel']
        if self.presets:
            args += [ '--presets', self.presets ]
        return self.subprocess(args, out, _in)

