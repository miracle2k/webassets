from __future__ import absolute_import

from mako.runtime import supports_caller

@supports_caller
def assets(context, env=None, bundles=None):
    if not bundles:
        raise ValueError("You need to provide at least one bundle")

    if not env:
        raise ValueError("You need to pass the webasset environment")

    assets = [x.strip() for x in bundles.split(',')]

    for name in assets:
        if name in env:
            for url in env[name].urls():
                context['caller'].body(ASSETS_URL=url)
        else:
            src = env.resolver.resolve_source(name)
            env.resolver.resolve_source_to_url(src, name)

    return ''
