"""As an optional feature, we can try to keep track of the assets used. This
makes it easier to run a manual rebuild.

In the future, it can also help deciding when an asset needs an automatic
update. For instance:
    - We might auto update when the hash changes, wheras the old hash to
      compare against will be stored by the tracker.
    - We might use the tracked assets to compare timestamps if that turns
      out to be faster than a stat() call.
    - Right now, if asset properties like the applied filters or the list
      of source files change, without causing the source timestamp to
      change, the update will not be automatically picked up. As those
      information could be tracked and then be used to detect changes.
"""

from djutils.features.assets.conf import settings

def get_tracker(name=None):
    """Return a callable(output, sources) that returns True if the file
    ``output``, based on the files in the list ``sources`` needs to be
    recreated.

    See the ``TRACK_ASSETS`` setting for more information.
    """
    if not name:
        name = settings.TRACK_ASSETS

    try:
        return {
            None: do_not_track,
            False: do_not_track,
            "model": track_via_model,
            "cache": track_via_cache,
            }[name]
    except KeyError:
        raise ValueError('Tracking option "%s" is not valid.' % name)

def do_not_track(*args, **kwargs):
    return None

def track_via_model(sourcefiles, outputfile, filter_name):
    raise NotImplementedError()
    """touched_time = current_ts()
    asset, created = Asset.objects.get_or_create(outputfile, [sourcefiles, filter_name, touched_time])
    if not created:
        asset.sourcefiles = sourcefiles
        asset.filter_name = filter_name
        asset.touched_mtime = touched_time
        asset.save()"""

def track_via_cache(sourcefiles, outputfile, filter_name):
    raise NotImplementedError()