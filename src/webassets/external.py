import os
from os import path
from merge import FileHunk

from exceptions import ExternalAssetsError, BuildError
from container import Container

__all__ = ('ExternalAssets',)


class ExternalAssets(Container):

    def __init__(self, *contents, **options):
        super(Container, self).__init__()
        self.env = None
        self.contents = contents
        self.output = options.pop('output', None)
        if options:
            raise TypeError("got unexpected keyword argument '%s'" %
                            options.keys()[0])
        self.extra_data = {}

    def __repr__(self):
        return "<%s folders=%s>" % (
            self.__class__.__name__,
            self.contents,
        )

    def get_versioned_file(self, file_name):
        version = self.get_version(file_name)
        bits = file_name.split('.')
        bits.insert(len(bits) - 1, version)
        return '.'.join(bits)

    def versioned_folder(self, file_name):
        if self.output:
            output_folder = self.output
        else:
            output_folder = self.env.config.get('external_assets_output_folder', None)
        if output_folder is None:
            raise ExternalAssetsError(
                'You must set an output folder for these ExternalAssets '
                'or the external_assets_output_folder config value')
        versioned = self.get_versioned_file(file_name)
        return path.join(output_folder, path.basename(versioned))

    def get_resolved_path(self, file_name):
        return self.env.resolver.resolve_source(file_name)

    def write_file(self, file_name):
        hunk = FileHunk(file_name)
        output_path = path.join(self.env.directory, self.versioned_folder(file_name))
        output_dir = path.dirname(output_path)
        if not path.exists(output_dir):
            os.makedirs(output_dir)
        hunk.save(output_path)
        if self.env.manifest:
            self.env.manifest.remember_file(file_name, self.env, self.get_version(file_name))

    def write_files(self, external_assets_path):
        resolved_paths = self.get_resolved_path(external_assets_path)
        if type(resolved_paths) is not list:
            resolved_paths = [resolved_paths]
        for path in resolved_paths:
            self.write_file(path)

    def build(self, env=None, force=None, disable_cache=None):
        # Prepare contents
        resolved_contents = self.resolve_contents(env, force=True)
        if not resolved_contents:
            raise BuildError('empty external assets cannot be built')
        for relpath, abspath in resolved_contents:
            self.write_files(relpath)

    def show_manifest(self):
        if self.env.manifest:
            print self.env.manifest.get_manifest()

    def url(self, file_name):
        versioned = self.versioned_folder(file_name)
        url = self.env.resolver.resolve_output_to_url(versioned)
        file_path = self.env.resolver.resolve_source(file_name)
        if not path.exists(file_path):
            self.write_file(file_path)
        return url

    def get_version(self, file_name):
        version = None
        if self.env.manifest:
            version = self.env.manifest.query_file(file_name, self.env)
        if version is None:
            version = self.env.versions.determine_file_version(file_name, self.env)
        return version

    @property
    def is_container(self):
        """ExternalAssets cannot be containers
        """
        return False
