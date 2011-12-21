#!/usr/bin/env python
from os import path
from webassets import Bundle, Environment

env = Environment(path.join(path.dirname(__file__), 'static'), '/stylesheets')
# App Engine doesn't support automatic rebuilding.
env.updater = False
# URL expiry not currently supported on App Engine
env.expire = False

bundle = Bundle('in.css', filters="cssmin", output="out.css")
env.add(bundle)


if __name__== "__main__":
    # If this file is called directly, do a manual build.
    bundle.build()
