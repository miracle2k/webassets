"""Test the versioners and manifest implementations.
"""
import hashlib
import codecs
import os

from nose.tools import assert_raises

from webassets.env import Environment
from webassets.merge import MemoryHunk, FileHunk
from webassets.test import TempEnvironmentHelper
from webassets.version import (
    FileManifest, JsonManifest, CacheManifest, TimestampVersion,
    VersionIndeterminableError, HashVersion, get_versioner, get_manifest)


class TestBinaryHunks(TempEnvironmentHelper):
    BINARY_DATA = b'\x80\x90\xa0\xff'

    def setup(self):
        super(TestBinaryHunks, self).setup()
        self.bundle = self.mkbundle('in', depends=('dep'), output='out')

        self.name = 'in'
        dirs = os.path.dirname(self.path(self.name))
        if not os.path.exists(dirs):
            os.makedirs(dirs)
        f = codecs.open(self.path(self.name), 'wb')
        f.write(self.BINARY_DATA)
        f.close()

    def test_read_binary_file_hunk(self):
        h = FileHunk(self.path(self.name))
        d = h.data() 
        assert isinstance(d, str)
        assert d == self.BINARY_DATA

    def test_write_binary_file_hunk(self):
        outfile = self.path('out')
        h = FileHunk(self.path(self.name))
        h.save(outfile)

        with open(outfile, 'rb') as f:
            d = f.read()

        assert isinstance(d, str)
        assert d == self.BINARY_DATA

    def test_write_memory_hunk(self):
        outfile = self.path('out')
        h = MemoryHunk(self.BINARY_DATA)
        h.save(outfile)

        with open(outfile, 'rb') as f:
            d = f.read()

        assert isinstance(d, str)
        assert d == self.BINARY_DATA
