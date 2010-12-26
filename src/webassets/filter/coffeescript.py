import os, subprocess

from webassets.filter import Filter


__all__ = ('CoffeeScriptFilter',)


class CoffeeScriptFilter(Filter):
    """Converts `CoffeeScript <http://jashkenas.github.com/coffee-script/>`_ to real JavaScript.

    If you want to combine it with other JavaScript filters, make sure this
    one runs first.
    """

    name = 'coffeescript'

    def setup(self):
        self.coffee = self.get_config('COFFEE_PATH', what='coffee binary', require=False) or 'coffee'

    def input(self, _in, out, source_path, output_path):
        old_dir = os.getcwd()
        os.chdir(os.path.dirname(source_path))
        try:
            proc = subprocess.Popen([self.coffee, '-bp', source_path],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                raise Exception(('coffeescript: subprocess had error: stderr=%s, '+
                                'stdout=%s, returncode=%s') % (
                                                stderr, stdout, proc.returncode))
            elif stderr:
                print "coffeescript filter has warnings:", stderr
            out.write(stdout)
        finally:
            os.chdir(old_dir)
