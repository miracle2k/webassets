from webassets.filter import Filter
import re

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
            what='Wrap everything in a closure', require=False) or True
        
        self._include_jst_script = (self._template_function == 'template')

        self._templates = {}

    def input(self, _in, out, source_path, output_path):
        self._templates[source_path] = _in.read().replace('\r?\n', '\\n')\
            .replace("'", r"\'")

    def output(self, _in, out, **kwargs):
        self._find_base_paths()
        
        if not self._bare:
            out.write("(function(){\n    ")

        out.write("var %s = %s || {};\n" % (self._namespace, self._namespace))

        if self._include_jst_script:
            out.write("%s\n" % _jst_script)

        for path, contents in self._templates.iteritems():
            out.write("%s['%s'] = %s('%s');\n" % (self._namespace, 
                self._get_template_name(path), self._template_function, contents))
        
        if not self._bare:
            out.write("})();")

    def _find_base_paths(self):
        """Hmmm.  There should aways be some common base path."""
        paths = self._templates.keys()
        if len(paths) == 1:
            self._base_path = '/'.join(paths[0].split('/')[:-1])
        else:
            first = paths[0].split('/')
            last  = paths[-1].split('/')
            i = 0
            while first[i] == last[i] and i <= len(first):
                i += 1

            self._base_path = '/'.join(first[0:i])
    
    def _get_template_name(self, path):
        matches = re.findall(r'%s\/(.*)' % re.escape(self._base_path), path)
        return '.'.join(matches[0].split('.')[:-1])

_jst_script = 'var template = function(str){var fn = new Function(\'obj\', \'var \
__p=[],print=function(){__p.push.apply(__p,arguments);};\
with(obj||{}){__p.push(\\\'\'+str.replace(/\\\\/g, \'\\\\\\\\\')\
.replace(/\'/g, "\\\\\'").replace(/<%=([\\s\\S]+?)%>/g,\
function(match,code){return "\',"+code.replace(/\\\\\'/g, "\'")+",\'";})\
.replace(/<%([\\s\\S]+?)%>/g,function(match,code){return "\');"+code\
.replace(/\\\\\'/g, "\'").replace(/[\\r\\n\\t]/g,\' \')+"__p.push(\'";})\
.replace(/\\r/g,\'\\\\r\').replace(/\\n/g,\'\\\\n\')\
.replace(/\\t/g,\'\\\\t\')+"\');}return __p.join(\'\');");return fn;};'