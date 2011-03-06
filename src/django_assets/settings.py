"""Unfortunately, Sphinx's autodoc module does not allow us to extract
the docstrings from the various environment config properties and
displaying them under a custom title. Instead, it will always put the
docstrings under a "Environment.foo" header.

This module is a hack to work around the issue while avoiding to duplicate
the actual docstrings.
"""

from webassets import Environment

ASSETS_DEBUG = Environment.debug
ASSETS_CACHE = Environment.cache
ASSETS_UPDATER = Environment.updater
ASSETS_EXPIRE = Environment.expire
ASSETS_URL = Environment.url
ASSETS_ROOT = Environment.directory
