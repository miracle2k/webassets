import os
from itertools import takewhile


__all__ = ('common_path_prefix',)


def common_path_prefix(paths, sep=os.path.sep):
    """os.path.commonpath() is completely in the wrong place; it's
    useless with paths since it only looks at one character at a time,
    see http://bugs.python.org/issue10395

    This replacement is from:
        http://rosettacode.org/wiki/Find_Common_Directory_Path#Python
    """
    def allnamesequal(name):
        return all(n==name[0] for n in name[1:])
    bydirectorylevels = zip(*[p.split(sep) for p in paths])
    return sep.join(x[0] for x in takewhile(allnamesequal, bydirectorylevels))
