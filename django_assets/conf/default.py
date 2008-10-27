# Controls the output of the 'assets' templatetag.
# Possible values are:
#       ``False``       full production mode
#       "nomerge"       output all source assets separately
#       "nofilter"      merge the source asset, but do not apply filters
ASSETS_DEBUG = False

# Controls when an already cached asset should be recreated.
# Possible values are:
#       ``False``       do not recreate automatically (use the management
#                       command for a manual update)
#       "timestamp"     update if a source file timestamp exceeds the
#                       cache's timestamp
#       "hash"          update if the hash of a source file changes.
#                       requires TRACK_ASSETS="model"
#       "interval"      recreate after an interval X (in seconds), specify
#                       as a tuple:
#                       = ("internal", 3600)
#       "always"        always recreate an every request (avoid in
#                       production environments)
ASSETS_UPDATER = 'timestamp'

# Even if you disable automatic rebuilding of your assets via the
# ASSETS_UPDATER option, when an asset is found to be not (yet) existing,
# it would normally be created. You can set this option to ``False`` to
# disable the behaviour (and of the source files be rendered instead, as
# in ASSETS_DEBUG mode.
ASSETS_AUTO_CREATE = True

# If you send your assets to the client using a far future expires header
# to minimize the 304 responses your server has to send, you need to make
# sure that changed assets will be reloaded. This feature will help you.
# Possible values are:
#       ``False``       don't do anything, expires headers may cause problems
#       "querystring"   append a querystring with the assets last
#                       modification timestamp:
#                           asset.js?1212592199
#       "filename"      modify the assets filename to include the timestamp:
#                           asset.1212592199.js
#                       this may work better with certain proxies/browsers,
#                       but requires you to configure your webserver to
#                       rewrite those modified filenames to the originals.
#						see also: http://www.stevesouders.com/blog/2008/08/23/revving-filenames-dont-use-querystring/
ASSETS_EXPIRE = False

# Certain features require (or work better with) knowledge of used assets.
# Using this option, the assets templatetag will attempt to keep track and
# log all assets currently in use by your project.
# Possible values are:
#       ``False``       do not track assets
#       "cache"         using Django's caching framework
#       "model"         using a dedicated model for this purpose
TRACK_ASSETS = False

# If you are using django-assets with Jinja *and* want to the the "parse
# templates" functionality of the management command, then you need to
# specify which extensions you are using (since there is no "one way" to
# integrate Jinja with Django, this cannot be determined automatically).
ASSETS_JINJA2_EXTENSIONS = []