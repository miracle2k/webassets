"""
Generally speaking, compass provides a command line util that is used
  a) as a management script (like django-admin.py) doing for example
    setup work, adding plugins to a project etc), and
  b) can compile the sass source files into CSS.

While generally project-based, starting with 0.10, compass supports
compiling individual files, which is what we are using. Alternative
approaches would include:
   *) Using the "sass" filter to compile source files, setting it up
      to use the compas environment (framework files, sass extensions).
	*) Support a CompassBundle() which would call the compass utility to
      update a project, then further process the CSS outputted by compass.
See also this discussion:
http://groups.google.com/group/compass-users/browse_thread/thread/daf55acda03656d1
"""


import time
import os, subprocess
from os import path
import tempfile

from django_assets.filter import Filter


__all__ = ('CompassFilter',)


class CompassFilter(Filter):
    """Converts `Compass <http://compass-style.org/>`_ .sass files to
    CSS.

    Requires at least version 0.10.

    To compile a standard compass project, you only need to have
    django-assets compile your main ``screen.sass``, ``print.sass``
    and ``ie.sass`` files. All the partials that you include will
    be handled by compass.

    If you want to combine the filter with other CSS filters, make
    sure this one runs first.

    **Note**: Currently, this needs to be the very first filter
    applied. Changes by filters that ran before will be lost.
    """

    # XXX: See the less filter as to how we might deal with the "needs
    # to be first" issue.

    name = 'compass'

    def __init__(self):
        self.compass = self.get_config('COMPASS_BIN', what='compass binary',
                                       require=False) or 'compass'

    def input(self, _in, out, source_path, output_path):
        """Compass currently doesn't take data from stdin, and doesn't allow
        us from stdout either.

        Also, there's a bunch of other issues we need to work around:
         - compass doesn't support given an explict output file, only a
           "--css-dir" output directory.
         - The output filename used is based on the input filename, and
           simply cutting of the length of the "sass_dir" (and changing
           the file extension). That is, compass expects the input
           filename to always be inside the "sass_dir" (which defaults to
           ./src), and if this is not the case, the output filename will
           be gibberish (missing characters in front).

        As a result, we need to set both the --sass-dir and --css-dir
        options properly, so we can "guess" the final css filename.
        """
        sasspath = tempfile.mkdtemp()
        sassname = path.join(sasspath, 'in.sass')

        # Write the incoming stream to the temporary sass directory.
        f = open(sassname, 'wb')
        try:
            f.write(_in.read())
            f.flush()
        finally:
            f.close()

        proc = subprocess.Popen([self.compass, 'compile',
                                 '--sass-dir', sasspath,
                                 '--css-dir', sasspath,
                                 '--quiet',
                                 '--boring',
                                 '--output-style', 'expanded',
                                 sassname],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                # shell: necessary on windows to execute
                                # ruby files, but doesn't work on linux.
                                shell=(os.name == 'nt'))
        stdout, stderr = proc.communicate()

        # compass seems to always write a utf8 header? to stderr, so
        # make sure to not fail just because there's something there.
        if proc.returncode != 0:
            raise Exception(('compass: subprocess had error: stderr=%s, '+
                            'stdout=%s, returncode=%s') % (
                                            stderr, stdout, proc.returncode))


        f = open("%s.css" % path.splitext(sassname)[0])
        try:
            out.write(f.read())
        finally:
            f.close()
