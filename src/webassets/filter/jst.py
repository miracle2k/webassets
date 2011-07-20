from webassets.filter import Filter
import re

__all__ = ('JSTFilter',)


class JSTFilter(Filter):
    """`Jammit Style <http://documentcloud.github.com/jammit/#jst>`_ JavaScript 
    templates. For a list of files, pulls out their contents and creates a 
    JavaScript object where the key is the name of the file. 
    
    Config options: 
        
        * `JST_NAMESPACE` to specify what the templates variable 
        should be called in the output (Defaults to `Templates`).
        * `JST_TEMPLATE_FUNCTION` to specify which templating function to use
        (Defaults to _.template)
    """
    name = 'jst'

    def setup(self):
        self._template_func = self.get_config('JST_TEMPLATE_FUNCTION', what='jst template func', require=False) or '_.template'
        self._namespace = self.get_config('JST_NAMESPACE', require=False) or 'Templates'
        self.templates = {}

    def input(self, _in, out, source_path, output_path):
        tpl_name = re.findall(r'templates/(.*)\.(.*)', source_path)[0][0]
        fp = open(source_path, 'r')
        contents = fp.read()
        fp.close()
        self.templates[tpl_name] = contents.replace('\n', '\\n').replace("'", r"\'")

    def output(self, _in, out, **kwargs):
        out.write('var %s = {};\n' % (self._namespace))
        for i, (name, contents) in enumerate(self.templates.iteritems()):
            out.write("%s['%s'] = %s('%s');\n" % (self._namespace, name, self._template_func, contents))