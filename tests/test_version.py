"""Test the versioners and manifest implementations.
"""
import hashlib

import os
from nose.tools import assert_raises

from webassets.env import Environment
from webassets.merge import MemoryHunk
from webassets.test import TempEnvironmentHelper
from webassets.version import (
    FileManifest, JsonManifest, CacheManifest, TimestampVersion,
    VersionIndeterminableError, HashVersion, get_versioner, get_manifest)


def test_builtin_version_accessors():
    assert get_versioner('hash').__class__ == HashVersion
    assert get_versioner('hash:15').length == 15
    assert get_versioner('timestamp').__class__ == TimestampVersion

    # [Regression]
    assert get_versioner('hash').length != None


def test_builtin_manifest_accessors():
    env = Environment('', '')
    assert get_manifest('cache', env).__class__ == CacheManifest
    assert get_manifest('file', env).__class__ == FileManifest
    assert get_manifest('file:/tmp/foo', env).filename == '/tmp/foo'


class TestTimestampVersion(TempEnvironmentHelper):

    def setup(self):
        super(TestTimestampVersion, self).setup()
        self.v = TimestampVersion()

        # Create a bunch of files with known mtimes
        self.create_files(['in', 'dep'])
        self.source_max = now = self.setmtime('dep')
        self.setmtime('in', mtime=now-100)
        self.bundle = self.mkbundle('in', depends=('dep'), output='out')

    def test_with_hunk(self):
        # If a hunk indicates call during a build, the output file is ignored,
        # and the versioner looks at the source files.
        self.create_files([self.bundle.output])
        self.setmtime(self.bundle.output, mtime=self.source_max+100)
        hunk = MemoryHunk('foo')
        assert self.v.determine_version(
            self.bundle, self.env, hunk) == int(self.source_max)

    def test_no_placeholder(self):
        # If output name contains no placeholder, the output file will be used
        # to determine the timestamp.
        self.create_files(['out'])
        self.setmtime('out', mtime=self.source_max+100)
        assert self.v.determine_version(
            self.bundle, self.env, None) == int(self.source_max+100)

        # What if the output file does not exist? (this should not happen, right?)
        self.unlink('out')
        assert_raises(OSError, self.v.determine_version,
            self.bundle, self.env, None)

    def test_with_placeholder(self):
        # If output name contains a placeholder, only source files can be used.
        self.bundle.output = 'out-%(version)s'
        assert self.v.determine_version(
            self.bundle, self.env, None) == int(self.source_max)

        # If any source file is missing, the updater cannot do its job.
        self.unlink('dep')
        assert_raises(VersionIndeterminableError, self.v.determine_version,
            self.bundle, self.env, None)

    def test_outputfile_timestamp(self):
        """The timestamp versioner ensures that an output file after being
        built has an mtime that reflects the version (the maximum mtime
        of the sources), NOT the current system time.
        """
        # Make sure that all source files have dates in the past, so we don't
        # pass this test by accident.
        source_max = self.setmtime('in', mod=-100)
        bundle = self.mkbundle('in', output='out')

        # Make sure our versioner is used
        self.env.versions = self.v

        bundle.build(force=True)
        # Only expect second precision
        assert int(os.path.getmtime(self.path('out'))) == int(source_max)


class TestHashVersion(TempEnvironmentHelper):

    def setup(self):
        super(TestHashVersion, self).setup()
        self.v = HashVersion()

        # Create a bunch of files with known content
        self.create_files({'in': '', 'dep': ''})
        self.bundle = self.mkbundle('in', depends=('dep'), output='out')

    def test_options(self):
        """Test customization options."""
        hunk = MemoryHunk('foo')
        assert HashVersion(length=None).determine_version(
            self.bundle, self.env, hunk) == 'acbd18db4cc2f85cedef654fccc4a4d8'
        assert HashVersion(length=2).determine_version(
            self.bundle, self.env, hunk) == 'ac'
        assert HashVersion(hash=hashlib.sha256).determine_version(
            self.bundle, self.env, hunk) == '2c26b46b'

    def test_with_hunk(self):
        # If a hunk is given, the has will be based on it, not the output file
        self.create_files({self.bundle.output: 'bar'})
        hunk = MemoryHunk('foo')
        assert self.v.determine_version(
            self.bundle, self.env, hunk) == 'acbd18db'

    def test_no_placeholder(self):
        # If output contains no placeholder, the output file will be hashed
        self.create_files({'out': 'rummpummpum'})
        assert self.v.determine_version(
            self.bundle, self.env, None) == '93667b60'

        # What if the output file does not exist? (this should not happen, right?)
        self.unlink('out')
        assert_raises(IOError, self.v.determine_version,
            self.bundle, self.env, None)

    def test_with_placeholder(self):
        # The HashVersion cannot function in this case.
        self.bundle.output = 'out-%(version)s'
        assert_raises(VersionIndeterminableError, self.v.determine_version,
            self.bundle, self.env, None)


class TestFileManifest(TempEnvironmentHelper):

    def setup(self):
        super(TestFileManifest, self).setup()
        self.bundle = self.mkbundle(output='foo')

    def test_repl(self):
        """Test simple in and out."""
        bundle = self.bundle
        manifest = FileManifest.make(self.env, 'manifest')

        # None is returned for missing information
        assert manifest.query(bundle, self.env) is None

        # Store something, validate we get it back
        manifest.remember(bundle, self.env, 'the-version')
        assert manifest.query(bundle, self.env) == 'the-version'

        # Recreate the manifest to ensure it has been written to disc
        manifest = FileManifest.make(self.env, 'manifest')
        assert manifest.query(bundle, self.env) == 'the-version'

    def test_cached_in_memory(self):
        """Test that the manifest is cached in memory."""
        manifest = FileManifest.make(self.env, 'manifest')
        manifest.remember(self.bundle, self.env, 'the-version')

        # After deleting the manifest file, we can still access the value
        self.env.auto_build = False
        self.unlink('manifest')
        assert manifest.query(self.bundle, self.env) == 'the-version'

        # However, if auto_build is enabled, the manifest is reloaded
        self.env.auto_build = True
        assert manifest.query(self.bundle, self.env) is None


class TestJsonManifest(TempEnvironmentHelper):

    def setup(self):
        super(TestJsonManifest, self).setup()
        self.bundle = self.mkbundle(output='foo')

    def test_repl(self):
        """Test simple in and out."""
        bundle = self.bundle
        manifest = JsonManifest.make(self.env, 'manifest')

        # None is returned for missing information
        assert manifest.query(bundle, self.env) is None

        # Store something, validate we get it back
        manifest.remember(bundle, self.env, 'the-version')
        assert manifest.query(bundle, self.env) == 'the-version'

        # Recreate the manifest to ensure it has been written to disc
        manifest = JsonManifest.make(self.env, 'manifest')
        assert manifest.query(bundle, self.env) == 'the-version'


class TestCacheManifest(TempEnvironmentHelper):

    def setup(self):
        super(TestCacheManifest, self).setup()
        self.bundle = self.mkbundle(output='foo')

    def test_repl(self):
        """Test simple in and out."""
        manifest = CacheManifest()
        self.env.cache = True

        # None is returned for missing information
        assert manifest.query(self.bundle, self.env) is None

        # Store something, validate we get it back
        manifest.remember(self.bundle, self.env, 'the-version')
        assert manifest.query(self.bundle, self.env) == 'the-version'

    def test_no_cache_attached(self):
        """Test behavior or CacheManifest if no cache is available."""
        manifest = CacheManifest()

        # If no cache is enabled, an error is raised
        self.env.cache = False
        assert_raises(EnvironmentError,
            manifest.remember, self.bundle, self.env, 'the-version')
        assert_raises(EnvironmentError,
            manifest.query, self.bundle, self.env)
