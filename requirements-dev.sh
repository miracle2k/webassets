#!/bin/sh

set -e

# External filter binaries to install for testing.

# Disable, because there are issues with the install on Travis CI.
#gem install sass --version 3.2.19
#gem install compass --version 0.12.6


# Only install NodeJS version by default.
#gem install less --version 1.2.21

# Node dependencies
npm install
