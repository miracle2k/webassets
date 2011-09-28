import os
import re
from webassets.filter import Filter
from webassets.utils import common_path_prefix


__all__ = ('JSTFilter',)


class JSTFilter(Filter):
    """`Jammit Style <http://documentcloud.github.com/jammit/#jst>`_ JavaScript 
    templates. For a list of files, pulls out their contents and creates a 
    JavaScript object where the key is the name of the file.

    """
    name = 'jst'

    def setup(self):
        self._template_function = self.get_config('JST_COMPILER', 
            what='The JavaScript compiler function to use', 
            require=False) or 'template'

        self._namespace = self.get_config('JST_NAMESPACE', 
            what='The JavaScript namespace to put templates in', 
            require=False) or 'window.JST'
        
        self._bare = self.get_config('JST_BARE', 
            what='Wrap everything in a closure', require=False)
        if self._bare is None:
            self._bare = True
        
        self._include_jst_script = (self._template_function == 'template')

        self._templates = []

    def input(self, _in, out, source_path, output_path):
        data = _in.read()
        self._templates.append(
            (source_path, data.replace('\n', '\\n').replace("'", r"\'")))

    def output(self, _in, out, **kwargs):
        base_path = self._find_base_path() + os.path.sep

        if not self._bare:
            out.write("(function(){\n    ")

        out.write("%s = %s || {};\n" % (self._namespace, self._namespace))

        if self._include_jst_script:
            out.write("%s\n" % _jst_script)

        for path, contents in self._templates:
            out.write("%s['%s'] = %s('%s');\n" % (self._namespace, 
                os.path.splitext(path[len(base_path):])[0],
                self._template_function, contents))
        
        if not self._bare:
            out.write("})();")

    def _find_base_path(self):
        """Hmmm.  There should aways be some common base path."""
        paths = [path for path, content in self._templates]
        if len(paths) == 1:
            return os.path.dirname(paths[0])
        return common_path_prefix(paths)


_jst_script = 'var template = function(str){var fn = new Function(\'obj\', \'var \
__p=[],print=function(){__p.push.apply(__p,arguments);};\
with(obj||{}){__p.push(\\\'\'+str.replace(/\\\\/g, \'\\\\\\\\\')\
.replace(/\'/g, "\\\\\'").replace(/<%=([\\s\\S]+?)%>/g,\
function(match,code){return "\',"+code.replace(/\\\\\'/g, "\'")+",\'";})\
.replace(/<%([\\s\\S]+?)%>/g,function(match,code){return "\');"+code\
.replace(/\\\\\'/g, "\'").replace(/[\\r\\n\\t]/g,\' \')+"__p.push(\'";})\
.replace(/\\r/g,\'\\\\r\').replace(/\\n/g,\'\\\\n\')\
.replace(/\\t/g,\'\\\\t\')+"\');}return __p.join(\'\');");return fn;};'
