import os
from os import path
from merge import FileHunk

try:
    # Current version of glob2 does not let us access has_magic :/
    import glob2 as glob
    from glob import has_magic
except ImportError:
    import glob
    from glob import has_magic

__all__ = ('ExternalAssets',)

class ExternalAssets(object):

    def __init__(self, folders):
        
        self.folders = folders
        #self.version = options.pop('version', [])

    def get_versioned_file(self, file_name):
        version = self.get_version(file_name)
        bits = file_name.split('.')
        bits.insert(len(bits)-1, version)
        return '.'.join(bits)
        
    def get_output_path(self, file_name):
        return self.env.abspath(self.get_versioned_file(file_name))

    def write_file(self, file_name):
        output_path = self.get_output_path(file_name)
        hunk = FileHunk(self.env.abspath(file_name))
        output_path = output_path.replace('img/','genimg/')
        output_dir = path.dirname(output_path)
        if not path.exists(output_dir):
            os.makedirs(output_dir)
        hunk.save(output_path)
        if self.env.manifest:
            self.env.manifest.remember_file(file_name, self.env, self.get_version(file_name))

    def write_files(self):
        for folder in self.folders:
            path = self.env.abspath(folder)
            for file_name in glob.glob(path):
                self.write_file(file_name.replace('%s/' % self.env.abspath(''),''))

    def show_manifest(self):
        if self.env.manifest:
            print self.env.manifest.get_manifest()

    def url(self, file_name):
        return self.env.absurl(self.get_versioned_file(file_name))

    def get_version(self, file_name):
        return self.env.versions.determine_file_version(file_name, self.env)