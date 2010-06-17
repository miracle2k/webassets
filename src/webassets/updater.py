"""An "updater" determines when assets should automatically be recreated.
"""

import os


def get_updater(name):
    """Return a callable(output, sources) that returns True if the file
    ``output``, based on the files in the list ``sources`` needs to be
    recreated.
    """
    if callable(name):
        return name

    try:
        return {
            None: update_never,
            False: update_never,
            "never": update_never,
            "timestamp": update_by_timestamp,
            "hash": update_by_hash,
            "interval": update_by_interval,
            "always": update_always
            }[name]
    except KeyError:
        raise ValueError('Updater "%s" is not valid.' % name)

def update_never(*args):
    return False

def update_always(*args):
    return True

def update_by_timestamp(output, sources):
    o_modified = os.stat(output).st_mtime
    s_modified = max([os.stat(s).st_mtime for s in sources])
    # TODO: What about using != - could that potentially be more solid?
    return s_modified > o_modified

def update_by_hash(output, sources):
    raise NotImplementedError()

def update_by_interval(output, sources):
    raise NotImplementedError()