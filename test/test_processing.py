"""Testing the ``bundle_to_joblist`` method directly lets us ensure
certain behavioral aspects more easily then testing on a higher level
where we have to deal with actual files.
"""

from nose.tools import assert_raises, with_setup

from django_assets import Bundle
from django_assets.bundle import BundleError
from django_assets.merge import bundle_to_joblist
from django_assets.conf import settings
from django_assets.filter import Filter


def with_config(**options):
    """Decorator to run a test with the given config options, resetting
    at the end of the test.
    """
    def decorator(func):
        old = {}
        def setup():
            for k, v in options.iteritems():
                old[k] = getattr(settings, k, None)
                setattr(settings, k, v)
        def teardown():
            for k, v in old.iteritems():
                setattr(settings, k, v)
        return with_setup(setup, teardown)(func)
    return decorator


# Dummy filter funcs to use during these tests.
class DummyFilter(Filter):
    def __init__(self, name):
        self.name = name
    def unique(self):
        return self.name
css = DummyFilter('css')
js = DummyFilter('js')
sass = DummyFilter('sass')


def test_flat():
    """If the bundle structure is already flat, we don't have to do much.
    """
    b = Bundle('s1', 'a2', output='foo')
    jl = bundle_to_joblist(b)
    assert len(jl) == 1
    assert jl.keys()[0] == 'foo'
    assert len(jl['foo']) == 1
    assert len(jl['foo'][0][1]) == 2


def test_nested():
    """If the bundle structure is nested, it is flattened.
    """
    b = Bundle('s1', Bundle('s2', Bundle('s3')), output='foo')
    jl = bundle_to_joblist(b)
    assert len(jl) == 1
    assert jl.keys()[0] == 'foo'
    assert len(jl['foo']) == 3
    assert jl['foo'][0][1] == ['s1']
    assert jl['foo'][1][1] == ['s2']
    assert jl['foo'][2][1] == ['s3']


def test_filter_merge():
    """Test that filter lists in a nested bundle structure are
    properly merged.
    """
    b = Bundle('s1',
               Bundle('s2',
                      Bundle('s3', filters=[css, sass]),
                      filters=[js]),
               output='foo')
    jl = bundle_to_joblist(b)
    assert jl['foo'][0][0] == []
    assert jl['foo'][0][1] == ['s1']
    assert jl['foo'][1][0] == [js]
    assert jl['foo'][1][1] == ['s2']
    assert jl['foo'][2][0] == [css, sass, js]
    assert jl['foo'][2][1] == ['s3']


def test_no_output():
    """Each file in a bundle needs an output target if it is supposed
    to be merged. An error is raised if no target is available.
    """

    # The root bundle is lacking an output option.
    assert_raises(BundleError, bundle_to_joblist, Bundle('s1', 's2'))

    # Also, if the output is missing merely in a subtree, that's ok.
    bundle_to_joblist(Bundle('s1', Bundle('s2'), output='foo'))

    # If the root bundle is merely a container, that's ok, as long as
    # all the sub-bundles have their own output target.
    bundle_to_joblist(Bundle(
        Bundle('s1', output='foo'),
        Bundle('s2', output='bar')))
    assert_raises(BundleError, bundle_to_joblist, Bundle(
        Bundle('s1', output='foo'),
        Bundle('s2')))


@with_config(DEBUG=True, ASSETS_DEBUG=True)
def test_no_output_no_merge():
    """A missing output target is ok as long as no merge is required.
    """
    bundle_to_joblist(Bundle('s1', 's2'))


def test_duplicate_output():
    """An error is raised if within a single bundle, two jobs override
    each other.
    """
    assert_raises(BundleError, bundle_to_joblist, Bundle(
        Bundle('s1', output='foo'),
        Bundle('s2', output='foo')))


def test_no_output_but_filters():
    """If a container specifies filters, those filters are applied to
    the sub-bundles.
    """
    jl = bundle_to_joblist(Bundle(
            Bundle('s1', output='foo'),
            Bundle('s2', output='bar', filters=[js]),
            filters=[css]))
    assert jl['foo'][0][0] == [css]
    assert jl['foo'][0][1] == ['s1']
    assert jl['bar'][0][0] == [js, css]
    assert jl['bar'][0][1] == ['s2']


@with_config(DEBUG=True, ASSETS_DEBUG=True)
def test_unmergable():
    """A subbundle that is unmergable will be pulled into a separate job.
    """
    b = Bundle('s1', 's2',
               Bundle('s3', debug=False, filters=css, output="bar"),
               output='foo', filters=js)
    jl = bundle_to_joblist(b)
    assert len(jl) == 3
    assert 's1' in jl and 's2' in jl
    assert jl['bar'][0][0] == [css]
    assert 's3' in jl['bar'][0][1]

    # However, the bundle that is pulled up needs to have it's own output
    # target, or we can't continue.
    assert_raises(BundleError, bundle_to_joblist,
                  Bundle('s1', Bundle('s2', debug=False), output='foo'))


@with_config(DEBUG=True, ASSETS_DEBUG='merge')
def test_debug_merge_only():
    """Test the 'merge only' debug option (no filters).
    """
    sub = Bundle('s3', filters=[css], output="bar")
    b = Bundle('s1', 's2', sub, output='foo', filters=[js])
    jl = bundle_to_joblist(b)
    assert len(jl) == 1
    assert jl['foo'][0][0] == []
    assert jl['foo'][1][0] == []

    sub.debug = False
    jl = bundle_to_joblist(b)
    assert len(jl) == 1
    assert jl['foo'][0][0] == []
    assert jl['foo'][1][0] == [css]

    sub.debug = True
    jl = bundle_to_joblist(b)
    assert len(jl) == 2
    assert jl['foo'][0][0] == []


@with_config(DEBUG=True, ASSETS_DEBUG=True)
def test_debug_inheritance():
    """Test the bundle ``debug`` setting in a nested scenario.
    """
    sub2 = Bundle('s4', filters=[js], output="bar")
    sub1 = Bundle('s3', sub2, debug='merge', output='foo', filters=[css])
    b = Bundle('s1', 's2', sub1, filters=[js])

    jl = bundle_to_joblist(b)
    assert len(jl) == 3
    assert 's1' in jl and 's2' in jl
    assert jl['foo'][0][0] == []
    assert jl['foo'][1][0] == []

    sub2.debug = True
    jl = bundle_to_joblist(b)
    assert len(jl) == 4
    assert 's1' in jl and 's2' in jl and 's4' in jl
    assert jl['foo'][0][0] == []