import os
import re
from webassets.filter import Filter
from webassets.utils import common_path_prefix


__all__ = ('JSTFilter',)


class JSTemplateFilter(Filter):
    """Common base class for the JST and Handlebars filters, and
    possibly other Javascript templating systems in the future.
    """

    def setup(self):
        super(JSTemplateFilter, self).setup()
        # Reset template collection (same instance may run multiple times)
        self.templates = []

    def _find_base_path(self, paths):
        """Hmmm.  There should aways be some common base path."""
        if len(paths) == 1:
            return os.path.dirname(paths[0])
        return common_path_prefix(paths)


class JSTFilter(JSTemplateFilter):
    """`Jammit Style <http://documentcloud.github.com/jammit/#jst>`_ JavaScript 
    templates. For a list of files, pulls out their contents and creates a 
    JavaScript object where the key is the name of the file.

    """
    name = 'jst'
    options = {
        # The JavaScript compiler function to use
        'template_function': 'JST_COMPILER',
        # The JavaScript namespace to put templates in
        'namespace': 'JST_NAMESPACE',
        # Wrap everything in a closure
        'bare': 'JST_BARE',
    }

    def setup(self):
        super(JSTFilter, self).setup()
        self.include_jst_script = \
            (self.template_function == 'template') or not self.template_function

    def input(self, _in, out, source_path, output_path, **kw):
        data = _in.read()
        self.templates.append((source_path, data))

        # Write back or the cache would not detect changes
        out.write(data)

    def output(self, _in, out, **kwargs):
        base_path = self._find_base_path() + os.path.sep
        namespace = self.namespace or 'window.JST'

        if self.bare == False:
            out.write("(function(){\n    ")

        out.write("%s = %s || {};\n" % (namespace, namespace))

        if self.include_jst_script:
            out.write("%s\n" % _jst_script)

        for path, contents in self.templates:
            # Make it a valid Javascript string. Is this smart enough?
            contents = contents.replace('\n', '\\n').replace("'", r"\'")
            out.write("%s['%s'] = %s('%s');\n" % (namespace,
                os.path.splitext(path[len(base_path):])[0],
                self.template_function or 'template', contents))
        
        if self.bare == False:
            out.write("})();")

    def _find_base_path(self):
        """Hmmm.  There should aways be some common base path."""
        paths = [path for path, content in self.templates]
        return JSTemplateFilter._find_base_path(self, paths)


_jst_script = 'var template = function(str){var fn = new Function(\'obj\', \'var \
__p=[],print=function(){__p.push.apply(__p,arguments);};\
with(obj||{}){__p.push(\\\'\'+str.replace(/\\\\/g, \'\\\\\\\\\')\
.replace(/\'/g, "\\\\\'").replace(/<%=([\\s\\S]+?)%>/g,\
function(match,code){return "\',"+code.replace(/\\\\\'/g, "\'")+",\'";})\
.replace(/<%([\\s\\S]+?)%>/g,function(match,code){return "\');"+code\
.replace(/\\\\\'/g, "\'").replace(/[\\r\\n\\t]/g,\' \')+"__p.push(\'";})\
.replace(/\\r/g,\'\\\\r\').replace(/\\n/g,\'\\\\n\')\
.replace(/\\t/g,\'\\\\t\')+"\');}return __p.join(\'\');");return fn;};'
