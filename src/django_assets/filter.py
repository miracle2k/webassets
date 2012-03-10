"""Django specific filters.

For those to be registered automatically, make sure the main
django_assets namespace imports this file.
"""

from django.template import Template, Context

from webassets.filter import Filter, register_filter



class TemplateFilter(Filter):
    """Will compile all source files as Django templates.
    """

    name = 'template'

    def __init__(self, context=None):
        super(TemplateFilter, self).__init__()
        self.context = context

    def input(self, _in, out, source_path, output_path, **kw):
        t = Template(_in.read(), origin='django-assets', name=source_path)
        out.write(t.render(Context(self.context if self.context else {}) ))


register_filter(TemplateFilter)
