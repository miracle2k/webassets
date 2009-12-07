from nose.tools import assert_raises
from django_assets import Bundle
from django_assets.filter import Filter


def test_filter_assign():
    """Test the different ways we can assign filters to the bundle.
    """

    class TestFilter(Filter):
        pass

    def _assert(list, length):
        """Confirm that everything in the list is a filter instance, and
        that the list as the required length."""
        assert len(list) == length
        assert bool([f for f in list if isinstance(f, Filter)])

    # Comma-separated string.
    b = Bundle(filters='jsmin,cssutils')
    _assert(b.filters, 2)

    # List of strings.
    b = Bundle(filters=['jsmin', 'cssutils'])
    _assert(b.filters, 2)
    # Strings inside a list may not be further comma separated
    assert_raises(ValueError, Bundle, filters=['jsmin,cssutils'])

    # A single or multiple classes may be given
    b = Bundle(filters=TestFilter)
    _assert(b.filters, 1)
    b = Bundle(filters=[TestFilter, TestFilter, TestFilter])
    _assert(b.filters, 3)

    # A single or multiple instance may be given
    b = Bundle(filters=TestFilter())
    _assert(b.filters, 1)
    b = Bundle(filters=[TestFilter(), TestFilter(), TestFilter()])
    _assert(b.filters, 3)

    # You can mix instances and classes
    b = Bundle(filters=[TestFilter, TestFilter()])
    _assert(b.filters, 2)

    # If something is wrong, an error is raised right away.
    assert_raises(ValueError, Bundle, filters='notreallyafilter')
    assert_raises(ValueError, Bundle, filters=object())

    # [bug] Specifically test that we can assign ``None``.
    Bundle().filters = None

    # Changing filters after bundle creation is no problem, either.
    b = Bundle()
    assert b.filters is None
    b.filters = TestFilter
    _assert(b.filters, 1)

    # Assigning the own filter list should change nothing.
    old_filters = b.filters
    b.filters = b.filters
    assert b.filters == old_filters