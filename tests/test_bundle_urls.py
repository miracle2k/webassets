"""Tests for the URL-generation aspect of :class:`Bundle`.

However, URL generation that is associated with a special feature is
more likely` found in `test_bundle_various.py``.
"""

from __future__ import with_statement

import re

import pytest

from tests.test_bundle_build import AppendFilter
from webassets import Bundle
from webassets.exceptions import BundleError
from webassets.test import TempEnvironmentHelper, TempDirHelper

# SRI for an empty file
_EMPTY_FILE_SRI = 'sha384-OLBgp1GsljhM2TJ+sbHjaiH9txEUvgdDTAzHv2P24donTt6/529l+9Ua0vFImLlb'


class BaseUrlsTester(TempEnvironmentHelper):
    """Baseclass to test the url generation

    It defines a mock bundle class that intercepts calls to build().
    This allows us to test the Bundle.url() method up to it calling
    into Bundle.build().
    """

    default_files = {'a': '', 'b': '', 'c': '', '1': '', '2': ''}

    def setup_method(self):
        super().setup_method()

        self.env.url_expire = False

        self.build_called = build_called = []
        self.makeurl_called = makeurl_called = []
        env = self.env

        class MockBundle(Bundle):
            def __init__(self, *a, **kw):
                Bundle.__init__(self, *a, **kw)
                self.env = env

            def _build(self, *a, **kw):
                build_called.append(self.output)

            def _make_url(self, *a, **kw):
                makeurl_called.append(self.output)
                return Bundle._make_url(self, *a, **kw)

        self.MockBundle = MockBundle


class TestUrlsVarious(BaseUrlsTester):
    """Other, general tests for the urls() method.

    The TestUrls()* classes test the logic behind urls(). The ``url_expire``
    option is part of ``TestVersionFeatures``.
    """

    def test_erroneous_debug_value(self):
        """Test the exception Bundle.urls() throws if debug is an invalid
        value."""
        # On the bundle level
        b = self.MockBundle('a', 'b', debug="invalid")
        pytest.raises(BundleError, b.urls, env=self.env)

        # On the environment level
        self.env.debug = "invalid"
        b = self.MockBundle('a', 'b')
        pytest.raises(BundleError, b.urls, env=self.env)

        # Self-check - this should work if this test works.
        self.env.debug = True  # valid again
        self.MockBundle('a', 'b', debug="merge").urls()

    def test_pass_down_env(self):
        """[Regression] When a root *container* bundle is connected
        to an environment, the child bundles do not have to be.
        """
        child = Bundle('1', '2')
        child.env = None
        root = self.MockBundle(child)
        root.env = self.env
        # Does no longer raise an "unconnected env" exception
        assert root.urls() == ['/1', '/2']

    def test_invalid_source_file(self):
        """If a source file is missing, an error is raised even when rendering
        the urls (as opposed to just outputting the url to the missing file
        (this is cached and only done once).

        It's helpful for debugging (in particular when rewriting takes place by
        things like the django-staticfiles extension, or Flask's blueprints).
        """
        self.env.debug = True
        bundle = self.mkbundle('non-existent-file', output="out")
        pytest.raises(BundleError, bundle.urls)

    def test_filters_in_debug_mode(self):
        """Test that if a filter is used which runs in debug mode, the bundle
        is forcibly merged (unless overridden)
        """
        self.env.debug = True
        test_filter = AppendFilter()
        bundle = self.MockBundle('a', filters=test_filter, output='out')

        # We get the source files...
        assert bundle.urls() == ['/a']
        assert len(self.build_called) == 0

        # ...until the filter is switched to 'always run'
        test_filter.max_debug_level = None
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

        # An explicit bundle debug=True overrides the behavior.
        bundle.debug = True
        assert bundle.urls() == ['/a']
        assert len(self.build_called) == 1  # no change

    def test_external_refs(self):
        """If a bundle contains absolute paths outside of the
        media directory, to generate a url they are copied in.
        """
        self.env.debug = True
        with TempDirHelper() as h:
            h.create_files(['foo.css'])
            bundle = self.mkbundle(h.path('foo.css'))
            urls = bundle.urls()
            assert len(urls) == 1
            assert re.match(r'.*/webassets-external/[\da-z]*_foo.css', urls[0])

    def test_external_refs_calculate_sri(self):
        """If a bundle contains absolute paths outside of the
        media directory, to generate a url they are copied in.
        """
        self.env.debug = True
        with TempDirHelper() as h:
            h.create_files(['foo.css'])
            bundle = self.mkbundle(h.path('foo.css'))
            urls = bundle.urls(calculate_sri=True)
            assert len(urls) == 1
            assert re.match(r'.*/webassets-external/[\da-z]*_foo.css', urls[0]['uri'])
            assert urls[0]['sri'] == _EMPTY_FILE_SRI


class TestUrlsWithDebugFalse(BaseUrlsTester):
    """Test url generation in production mode - everything is always built.
    """

    def test_simple_bundle(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_nested_bundle(self):
        bundle = self.MockBundle(
            'a', self.MockBundle('d', 'childout'), 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_container_bundle(self):
        """A bundle that has only child bundles and does not specify
        an output target of its own will simply build its child
        bundles separately.
        """
        bundle = self.MockBundle(
            self.MockBundle('a', output='child1'),
            self.MockBundle('a', output='child2'))
        assert bundle.urls() == ['/child1', '/child2']
        assert len(self.build_called) == 2

    def test_source_bundle(self):
        """If a bundle does neither specify an output target nor any
        filters, its file are always sourced directly.
        """
        bundle = self.MockBundle('a', self.MockBundle('d', output='childout'))
        assert bundle.urls() == ['/a', '/childout']
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_merge(self):
        """A bundle explicitly says it wants to be merged, wanting to override
        the  global "debug=False" setting. This is ineffectual (and anyway
        does not affect url generation).
        """
        bundle = self.MockBundle('1', '2', output='childout', debug='merge')
        assert bundle.urls() == ['/childout']
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_debug_true(self):
        """A bundle explicitly says it wants to be processed in debug
        mode, wanting overriding the global "debug=False" setting. This is
        ineffectual.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug=True)
        assert bundle.urls() == ['/childout']
        assert len(self.build_called) == 1

    def test_root_debug_true_and_child_debug_false(self):
        """The root bundle explicitly says it wants to be processed in
        debug mode, overriding the global "debug" setting, and a child
        bundle asks for debugging to be disabled again.

        None of this has any effect, since Environment.debug=False.
        """
        bundle = self.MockBundle(
            '1', '2',
            self.MockBundle('a', output='child1', debug=False),
            output='rootout', debug=True)
        assert bundle.urls() == ['/rootout']

    def test_simple_bundle_with_sri(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls(calculate_sri=True) == [{'uri': '/out', 'sri': None}]
        assert len(self.build_called) == 1

    def test_nested_bundle_with_sri(self):
        bundle = self.MockBundle(
            'a', self.MockBundle('d', 'childout'), 'c', output='out')
        assert bundle.urls(calculate_sri=True) == [{'uri': '/out', 'sri': None}]
        assert len(self.build_called) == 1

    def test_container_bundle_with_sri(self):
        """A bundle that has only child bundles and does not specify
        an output target of its own will simply build its child
        bundles separately.
        """
        bundle = self.MockBundle(
            self.MockBundle('a', output='child1'),
            self.MockBundle('a', output='child2'))
        assert bundle.urls(calculate_sri=True) == [{'uri': '/child1', 'sri': None},
                                                   {'uri': '/child2', 'sri': None}]
        assert len(self.build_called) == 2

    def test_source_bundle_with_sri(self):
        """If a bundle does neither specify an output target nor any
        filters, its file are always sourced directly.
        """
        bundle = self.MockBundle('a', self.MockBundle('d', output='childout'))
        # The child bundle generates a file, thus we end up being able to actually calculate the SRI in this case.
        assert bundle.urls(calculate_sri=True) == [
            {'uri': '/a', 'sri': 'sha384-OLBgp1GsljhM2TJ+sbHjaiH9txEUvgdDTAzHv2P24donTt6/529l+9Ua0vFImLlb'},
            {'uri': '/childout', 'sri': None}]
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_merge_with_sri(self):
        """A bundle explicitly says it wants to be merged, wanting to override
        the  global "debug=False" setting. This is ineffectual (and anyway
        does not affect url generation).
        """
        bundle = self.MockBundle('1', '2', output='childout', debug='merge')
        assert bundle.urls(calculate_sri=True) == [{'uri': '/childout', 'sri': None}]
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_debug_true_with_sri(self):
        """A bundle explicitly says it wants to be processed in debug
        mode, wanting overriding the global "debug=False" setting. This is
        ineffectual.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug=True)
        assert bundle.urls(calculate_sri=True) == [{'uri': '/childout', 'sri': None}]
        assert len(self.build_called) == 1

    def test_root_debug_true_and_child_debug_false_with_sri(self):
        """The root bundle explicitly says it wants to be processed in
        debug mode, overriding the global "debug" setting, and a child
        bundle asks for debugging to be disabled again.

        None of this has any effect, since Environment.debug=False.
        """
        bundle = self.MockBundle(
            '1', '2',
            self.MockBundle('a', output='child1', debug=False),
            output='rootout', debug=True)
        assert bundle.urls(calculate_sri=True) == [{'uri': '/rootout', 'sri': None}]


class TestUrlsWithDebugTrue(BaseUrlsTester):
    """Test url generation in debug mode.
    """

    def setup_method(self):
        super().setup_method()
        self.env.debug = True

    def test_simple_bundle(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls() == ['/a', '/b', '/c']
        assert len(self.build_called) == 0

    def test_nested_bundle(self):
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout'), 'c', output='out')
        assert bundle.urls() == ['/a', '/1', '/2', '/c']
        assert len(self.build_called) == 0

    def test_container_bundle(self):
        """A bundle that has only sub bundles and does not specify
        an output target of its own.
        """
        bundle = self.MockBundle(
            self.MockBundle('a', output='child1'),
            self.MockBundle('a', output='child2'))
        assert bundle.urls() == ['/a', '/a']
        assert len(self.build_called) == 0

    def test_url_source(self):
        """[Regression] Test a Bundle that contains a source URL.
        """
        bundle = self.MockBundle('http://test.de', output='out')
        assert bundle.urls() == ['http://test.de']
        assert len(self.build_called) == 0

        # This is the important test. It proves that the url source
        # was handled separately, and not processed like any other
        # source file, which would be passed through makeurl().
        # This is a bit convoluted to test because the code that
        # converts a bundle content into an url operates just fine
        # on a url source, so there is no easy other way to determine
        # whether the url source was treated special.
        assert len(self.makeurl_called) == 0

    def test_root_bundle_switching_to_debug_false(self):
        """A bundle explicitly says it wants to be processed with
        debug=False, overriding the global "debug=True" setting.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug=False)
        assert bundle.urls() == ['/childout']
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_merge(self):
        """A bundle explicitly says it wants to be merged, overriding
        the global "debug=True" setting.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug='merge')
        assert bundle.urls() == ['/childout']
        assert len(self.build_called) == 1

    def test_child_bundle_switching(self):
        """A child bundle explicitly says it wants to be processed in
        "merge" mode, overriding the global "debug=True" setting, with the
        root bundle not having an opinion.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug='merge'),
            'c', output='out')
        assert bundle.urls() == ['/a', '/childout', '/c']
        assert len(self.build_called) == 1

    def test_simple_bundle_with_sri(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls(calculate_sri=True) == [
                      {'sri': _EMPTY_FILE_SRI, 'uri': '/a'},
                      {'sri': _EMPTY_FILE_SRI, 'uri': '/b'},
                      {'sri': _EMPTY_FILE_SRI, 'uri': '/c'}]
        assert len(self.build_called) == 0

    def test_nested_bundle_with_sri(self):
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout'), 'c', output='out')
        assert bundle.urls(calculate_sri=True) == [{'sri': _EMPTY_FILE_SRI, 'uri': '/a'},
                                                   {'sri': _EMPTY_FILE_SRI, 'uri': '/1'},
                                                   {'sri': _EMPTY_FILE_SRI, 'uri': '/2'},
                                                   {'sri': _EMPTY_FILE_SRI, 'uri': '/c'}]
        assert len(self.build_called) == 0

    def test_container_bundle_with_sri(self):
        """A bundle that has only sub bundles and does not specify
        an output target of its own.
        """
        bundle = self.MockBundle(
            self.MockBundle('a', output='child1'),
            self.MockBundle('a', output='child2'))
        assert bundle.urls(calculate_sri=True) == [{'sri': _EMPTY_FILE_SRI, 'uri': '/a'},
                                                   {'sri': _EMPTY_FILE_SRI, 'uri': '/a'}]
        assert len(self.build_called) == 0

    def test_url_source_with_sri(self):
        """[Regression] Test a Bundle that contains a source URL.
        """
        bundle = self.MockBundle('http://test.de', output='out')
        assert bundle.urls(calculate_sri=True) == [{'sri': None, 'uri': 'http://test.de'}]
        assert len(self.build_called) == 0

        # This is the important test. It proves that the url source
        # was handled separately, and not processed like any other
        # source file, which would be passed through makeurl().
        # This is a bit convoluted to test because the code that
        # converts a bundle content into an url operates just fine
        # on a url source, so there is no easy other way to determine
        # whether the url source was treated special.
        assert len(self.makeurl_called) == 0

    def test_root_bundle_switching_to_debug_false_with_sri(self):
        """A bundle explicitly says it wants to be processed with
        debug=False, overriding the global "debug=True" setting.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug=False)
        assert bundle.urls(calculate_sri=True) == [{'sri': None, 'uri': '/childout'}]
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_merge_with_sri(self):
        """A bundle explicitly says it wants to be merged, overriding
        the global "debug=True" setting.
        """
        bundle = self.MockBundle('1', '2', output='childout', debug='merge')
        assert bundle.urls(calculate_sri=True) == [{'sri': None, 'uri': '/childout'}]
        assert len(self.build_called) == 1

    def test_child_bundle_switching_with_sri(self):
        """A child bundle explicitly says it wants to be processed in
        "merge" mode, overriding the global "debug=True" setting, with the
        root bundle not having an opinion.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug='merge'),
            'c', output='out')
        assert bundle.urls(calculate_sri=True) == [
                      {'sri': _EMPTY_FILE_SRI, 'uri': '/a'},
                      {'sri': None, 'uri': '/childout'},
                      {'sri': _EMPTY_FILE_SRI, 'uri': '/c'}]
        assert len(self.build_called) == 1


class TestUrlsWithDebugMerge(BaseUrlsTester):

    def setup_method(self):
        super().setup_method()
        self.env.debug = 'merge'

    def test_simple_bundle(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_nested_bundle(self):
        bundle = self.MockBundle('a', self.MockBundle('d', 'childout'), 'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_child_bundle_switching_to_debug_false(self):
        """A child bundle explicitly says it wants to be processed in
        full production mode, with overriding the global "debug" setting.

        This makes no difference to the urls that are generated.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug=False),
            'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_debug_true(self):
        """A bundle explicitly says it wants to be processed in debug mode,
        overriding the global ``debug=merge"`` setting. This is ineffectual.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug=True),
            'c', output='out')
        assert bundle.urls() == ['/out']
        assert len(self.build_called) == 1

    def test_simple_bundle_with_sri(self):
        bundle = self.MockBundle('a', 'b', 'c', output='out')
        assert bundle.urls(calculate_sri=True) == [{'sri': None, 'uri': '/out'}]
        assert len(self.build_called) == 1

    def test_nested_bundle_with_sri(self):
        bundle = self.MockBundle('a', self.MockBundle('d', 'childout'), 'c', output='out')
        assert bundle.urls(calculate_sri=True) == [{'sri': None, 'uri': '/out'}]
        assert len(self.build_called) == 1

    def test_child_bundle_switching_to_debug_false_with_sri(self):
        """A child bundle explicitly says it wants to be processed in
        full production mode, with overriding the global "debug" setting.

        This makes no difference to the urls that are generated.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug=False),
            'c', output='out')
        assert bundle.urls(calculate_sri=True) == [{'sri': None, 'uri': '/out'}]
        assert len(self.build_called) == 1

    def test_root_bundle_switching_to_debug_true_with_sri(self):
        """A bundle explicitly says it wants to be processed in debug mode,
        overriding the global ``debug=merge"`` setting. This is ineffectual.
        """
        bundle = self.MockBundle(
            'a', self.MockBundle('1', '2', output='childout', debug=True),
            'c', output='out')
        assert bundle.urls(calculate_sri=True) == [{'sri': None, 'uri': '/out'}]
        assert len(self.build_called) == 1
