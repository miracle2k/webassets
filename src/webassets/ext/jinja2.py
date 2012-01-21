from __future__ import absolute_import

import warnings
import jinja2
from jinja2.ext import Extension
from jinja2 import nodes
from webassets import Bundle
from webassets.loaders import GlobLoader, LoaderError
from webassets.exceptions import ImminentDeprecationWarning


__all__ = ('assets', 'Jinja2Loader',)


class AssetsExtension(Extension):
    """
    As opposed to the Django tag, this tag is slightly more capable due
    to the expressive powers inherited from Jinja. For example:

        {% assets "src1.js", "src2.js", get_src3(),
                  filter=("jsmin", "gzip"), output=get_output() %}
        {% endassets %}
    """

    tags = set(['assets'])

    BundleClass = Bundle   # Helpful for mocking during tests.

    def __init__(self, environment):
        super(AssetsExtension, self).__init__(environment)

        # add the defaults to the environment
        environment.extend(
            assets_environment=None,
        )

    def parse(self, parser):
        lineno = parser.stream.next().lineno

        files = []
        output = nodes.Const(None)
        filters = nodes.Const(None)
        dbg = nodes.Const(None)

        # parse the arguments
        first = True
        while parser.stream.current.type != 'block_end':
            if not first:
                parser.stream.expect('comma')
            first = False

            # lookahead to see if this is an assignment (an option)
            if parser.stream.current.test('name') and parser.stream.look().test('assign'):
                name = parser.stream.next().value
                parser.stream.skip()
                value = parser.parse_expression()
                if name == 'filters':
                    filters = value
                elif name == 'filter':
                    filters = value
                    warnings.warn('The "filter" option of the {%% assets %%} '
                                  'template tag has been renamed to '
                                  '"filters" for consistency reasons '
                                  '(line %s).' % lineno,
                                    ImminentDeprecationWarning)
                elif name == 'output':
                    output = value
                elif name == 'debug':
                    dbg = value
                else:
                    parser.fail('Invalid keyword argument: %s' % name)
            # otherwise assume a source file is given, which may
            # be any expression, except note that strings are handled
            # separately above
            else:
                files.append(parser.parse_expression())

        # parse the contents of this tag, and return a block
        body = parser.parse_statements(['name:endassets'], drop_needle=True)

        return nodes.CallBlock(
                self.call_method('_render_assets',
                                 args=[filters, output, dbg, nodes.List(files)]),
                [nodes.Name('ASSET_URL', 'store')], [], body).\
                    set_lineno(lineno)

    @classmethod
    def resolve_contents(self, contents, env):
        """Resolve bundle names."""
        result = []
        for f in contents:
            try:
                result.append(env[f])
            except KeyError:
                result.append(f)
        return result

    def _render_assets(self, filter, output, dbg, files, caller=None):
        env = self.environment.assets_environment
        if env is None:
            raise RuntimeError('No assets environment configured in '+
                               'Jinja2 environment')

        result = u""
        kwargs = {'output': output,
                  'filters': filter,
                }

        if dbg != None:
            kwargs['debug'] = dbg

        urls = self.BundleClass(*self.resolve_contents(files, env),
                                **kwargs).urls(env=env)
        for f in urls:
            result += caller(f)
        return result


assets = AssetsExtension  # nicer import name


class Jinja2Loader(GlobLoader):
    """Parse all the Jinja2 templates in the given directory, try to
    find bundles in active use.

    Try all the given environments to parse the template, until we
    succeed.
    """

    def __init__(self, assets_env, directories, jinja2_envs, charset='utf8'):
        self.asset_env = assets_env
        self.directories = directories
        self.jinja2_envs = jinja2_envs
        self.charset = charset

    def load_bundles(self):
        bundles = []
        for template_dir in self.directories:
            for filename in self.glob_files((template_dir, '*.html')):
                bundles.extend(self.with_file(filename, self._parse) or [])
        return bundles

    def _parse(self, filename, contents):
        for i, env in enumerate(self.jinja2_envs):
            try:
                t = env.parse(contents.decode(self.charset))
            except jinja2.exceptions.TemplateSyntaxError, e:
                #print ('jinja parser (env %d) failed: %s'% (i, e))
                pass
            else:
                result = []
                def _recurse_node(node_to_search):
                    for node in node_to_search.iter_child_nodes():
                        if isinstance(node, jinja2.nodes.Call):
                            if isinstance(node.node, jinja2.nodes.ExtensionAttribute)\
                               and node.node.identifier == AssetsExtension.identifier:
                                filter, output, files = node.args
                                bundle = Bundle(
                                    *AssetsExtension.resolve_contents(files.as_const(), self.asset_env),
                                    **{
                                        'output': output.as_const(),
                                        'filters': filter.as_const()})
                                result.append(bundle)
                        else:
                            _recurse_node(node)
                for node in t.iter_child_nodes():
                    _recurse_node(node)
                return result
        else:
            raise LoaderError('Jinja parser failed on %s, tried %d environments' % (
                filename, len(self.jinja2_envs)))
        return False
