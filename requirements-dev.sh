#!/bin/sh

set -e

# External filter binaries to install for testing.

# Disable, because there are issues with the install on Travis CI.
#gem install sass --version 3.2.19
#gem install compass --version 0.12.6


# Only install NodeJS version by default.
#gem install less --version 1.2.21

npm install -g postcss-cli
npm install -g autoprefixer
npm install -g less
npm install -g sass
npm install -g uglify-js@2.3.1
npm install -g coffee-script@1.6.2
npm install -g clean-css@1.0.2
npm install -g stylus
npm install -g handlebars
npm install -g typescript@3.7.2
npm install -g requirejs@2.1.11
npm install -g babel-cli@6.18.0 --save
# Don't install the babel-preset globally because
# there's a bug with older versions of node
npm install babel-preset-es2015@6.18.0
