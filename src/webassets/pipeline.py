from os import path
from bundle import Container, Bundle as Builder


__all__ = ('Bundle',)


class Bundle(Container):
    """A unit of asset source files. May contain Javascript and CSS files.
    """

    def __init__(self, *contents, **options):
        self.output = options.pop('output', None)
        super(Bundle, self).__init__(*contents, **options)

    @property
    def js(self):
        """A :class:`Builder` instance for the JavaScript contents of
        this bundle.

        You can use it to access the JavaScript urls::

            >>> bundle.js.urls()
            ('gen/default.ac4e3f.js',)

        .. note::
            The :class:`Builder`` instance is generated on-the-fly, and
            changes to it will be lost if the bundle itself is modified..
        """
        return self.get_builder('js')

    @property
    def css(self):
        """A :class:`Builder` instance for the stylesheet contents of
        this bundle.

        You can use it to access the CSS urls::

            >>> bundle.js.urls()
            ('gen/screen.fe3a81.css',)

        .. note::
            The :class:`Builder`` instance is generated on-the-fly, and
            changes to it will be lost if the bundle itself is modified..
        """
        return self.get_builder('css')

    def get_builder(self, type):
        """Return a :class:`Builder` for the parts of this bundle that belong
        to ``type``. The type will either be ``js`` or ``css``, but can in
        principle be an arbitrary identifier.

        The builder instance will be generated as needed, and cached until
        this bundle is modified.
        """
        # Create child builders for all files which need to be compiled first
        contents = []
        last_compilers = None
        for file in flatten_files(self):
            compilers, produced_type = inspect_filename(file)
            if produced_type != type:
                continue

            if not compilers:
                contents.append(file)
                last_compilers = None
            else:
                if compilers != last_compilers:
                    contents.append(Builder(filters=compilers))
                contents[-1].contents += (file,)

        # add compression filter for this type
        # add other essential filters (cssrewrite)
        # add optional filters (like daturi) via setting
        return Builder(*contents, output=self.output[type])


def flatten_files(bundle):
    # XXX remove any duplicates
    for item in bundle.contents:
        if isinstance(item, Container):
            for item in flatten_files(item):
                yield item
        else:
            yield item


"""
XXX Should obviously be based on what filters declare + maybe an env setting.

Filters would declare::

    class SassFilter():
        type = 'css'
        preprocess = ('.sass', '.scss')

And that would register globally/in the env as to dicts, maybe::

    extensions = {'.sass': SassFilter, '.scss': SassFilter}
    preprocess = {SassFilter: 'css'}

"""
COMPILERS = {
    'sass': 'sass',
    'scss': 'scss',
    'coffee': 'coffeescript',
    'jst': 'jst',
    'clever': 'clevercss'
}

PRODUCED_TYPES = {
    'sass': 'css',
    'scss': 'css',
    'clever': 'css',
    'jst': 'js',
    'coffee': 'js',
}

def inspect_filename(filename):
    """Looks at the extensions of ``filename``, and determines the list of
    filters that need to be applied to compile them.

    Returns a 2-tuple of (filter_list, produced_type).
    """
    filters = []
    last_encountered_type = None
    while True:
        rest, ext = path.splitext(filename)
        ext = ext[1:]  # remote leading dot
        if not ext:
            break
        if not ext in COMPILERS:
            last_encountered_type = PRODUCED_TYPES.get(ext, ext)
            # Stop on encountering an unknown extension
            break
        filters.append(COMPILERS[ext])
        last_encountered_type = PRODUCED_TYPES.get(ext, ext)
        filename = rest
    return filters, last_encountered_type


def run():
    jQuery = Bundle('/templates/*.jst')
    jQueryUI = Bundle(
        jQuery,
        'jquery.ui.js',
        'jquery.ui.accordion.js',
        'jquery.ui.accordion.css',
        'jquery.ui.datepicker.js',
        'jquery.ui.datepicker.de.js',
        'jquery.ui.datepicker.en.js',
        'jquery.ui.datepicker.css',
    )
    mySiteAssets = Bundle(
        'cssreset.css',
        jQuery,
        jQueryUI,
        'templates/*.jst',
        'pages/*.sass',
        'pages/*.coffee',
        output_js='gen/default.js', output_css='gen/screen.css',
        output={'js': 'default.js', 'css': 'screen.css'}
    )

    from webassets import Environment
    env = Environment(directory='/', url='/')
    env.auto_build = False
    env.debug = False
    env.url_expire = True
    env.cache = 'manifest.pickle'
    print mySiteAssets.css.urls(env=env)
    print mySiteAssets.js.urls(env=env)
