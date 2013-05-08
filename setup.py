#!/usr/bin/env python
import os
from setuptools import setup, find_packages
try:
    from itertools import imap as map, izip as zip
except ImportError:
    # Python3 has those in builtins.
    pass

try:
    from sphinx.setup_command import BuildDoc
    cmdclass = {'build_sphinx': BuildDoc}
except ImportError:
    cmdclass = {}


# Figure out the version. This could also be done by importing the
# module, the parsing takes place for historical reasons.
import re
here = os.path.dirname(os.path.abspath(__file__))
version_re = re.compile(
    r'__version__ = (\(.*?\))')
fp = open(os.path.join(here, 'src/webassets', '__init__.py'))
version = None
for line in fp:
    match = version_re.search(line)
    if match:
        version = eval(match.group(1))
        break
else:
    raise Exception("Cannot find version in __init__.py")
fp.close()


setup(
    name='webassets',
    version=".".join(map(str, version)),
    description='Media asset management for Python, with glue code for '+\
        'various web frameworks',
    long_description='Merges, minifies and compresses Javascript and '
        'CSS files, supporting a variety of different filters, including '
        'YUI, jsmin, jspacker or CSS tidy. Also supports URL rewriting '
        'in CSS files.',
    author='Michael Elsdoerfer',
    author_email='michael@elsdoerfer.com',
    license='BSD',
    url='http://github.com/miracle2k/webassets/',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
        ],
    entry_points="""[console_scripts]\nwebassets = webassets.script:run\n""",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    cmdclass=cmdclass,
)
