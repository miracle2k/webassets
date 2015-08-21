#!/bin/sh

# External filter binaries to install for testing.

# Disable, because there are issues with the install on Travis CI.
#gem install sass --version 3.2.19
#gem install compass --version 0.12.6


# Only install NodeJS version by default.
#gem install less --version 1.2.21

npm install -g less@2.5.1
npm install -g uglify-js@2.3.1
npm install -g coffee-script@1.6.2
npm install -g clean-css@1.0.2
npm install -g stylus
npm install -g handlebars
npm install -g typescript
npm install -g requirejs@2.1.11
