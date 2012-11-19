import os

from webassets.filter import Filter
from webassets.utils import working_directory


__all__ = ('PyScss',)


class PyScss(Filter):
    """Converts `Scss <http://sass-lang.com/>`_ markup to real CSS.

    This uses `PyScss <https://github.com/Kronuz/pyScss>`_, a native
    Python implementation of the Scss language. The PyScss module needs
    to be installed.

    This is an alternative to using the ``sass`` or ``scss`` filters,
    which are based on the original, external tools.

    .. note::
        The Sass syntax is not supported by PyScss. You need to use
        the ``sass`` filter based on the original Ruby implementation
        instead.

    *Supported configuration options:*

    PYSCSS_DEBUG_INFO (debug_info)
        Include debug information in the output for use with FireSass.

        If unset, the default value will depend on your
        :attr:`Environment.debug` setting.

    PYSCSS_LOAD_PATHS (load_paths)
        Additional load paths that PyScss should use.

        .. warning::
            The filter currently does not automatically use
            :attr:`Environment.load_path` for this.

    PYSCSS_ASSETS_ROOT (assets_root)
        The directory PyScss should look in when searching for things
        like images that you have referenced.. Will use
        :attr:`Environment.directory` by default.

    PYSCSS_ASSETS_URL (assets_url)
        The url PyScss should use when generating urls to files in
        ``PYSCSS_ASSETS_ROOT``. Will use :attr:`Environment.url` by
        default.
    """

    name = 'pyscss'
    options = {
        'debug_info': 'PYSCSS_DEBUG_INFO',
        'load_paths': 'PYSCSS_LOAD_PATHS',
        'assets_url': 'PYSCSS_ASSETS_URL',
        'assets_root': 'PYSCSS_ASSETS_ROOT',
    }
    max_debug_level = None

    def setup(self):
        super(PyScss, self).setup()

        import scss
        self.scss = scss

        # Initialize various settings:
        # Why are these module-level, not instance-level ?!

        # Only the dev version appears to support a list
        if self.load_paths:
            scss.LOAD_PATHS = ','.join(self.load_paths)

        # These are needed for various helpers (working with images
        # etc.). Similar to the compass filter, we require the user
        # to specify such paths relative to the media directory.
        scss.STATIC_URL = self.env.url
        scss.STATIC_ROOT = self.env.directory

        # This directory PyScss will use when generating new files,
        # like a spritemap. Maybe we should REQUIRE this to be set.
        scss.ASSETS_ROOT = self.assets_root or self.env.url
        scss.ASSETS_URL = self.assets_url or self.env.directory

    def input(self, _in, out, **kw):
        """Like the original sass filter, this also needs to work as
        an input filter, so that relative @imports can be properly
        resolved.
        """

        source_path = kw['source_path']

        # Because PyScss always puts the current working dir at first
        # place of the load path, this is what we need to use to make
        # relative references work.
        with working_directory(os.path.dirname(source_path)):

            scss = self.scss.Scss(
                scss_opts={
                    'compress': False,
                    'debug_info': (
                        self.env.debug if self.debug_info is None else self.debug_info),
                },
                # This is rather nice. We can pass along the filename,
                # but also give it already preprocessed content.
                scss_files={source_path: _in.read()})

            # Compile
            # Note: This will not throw an error when certain things
            # are wrong, like an include file missing. It merely outputs
            # to stdout, via logging. We might have to do something about
            # this, and evaluate such problems to an exception.
            out.write(scss.compile())
