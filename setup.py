import os
from distutils.core import setup
try:
    from sphinx.setup_command import BuildDoc
    cmdclass = {'build_sphinx': BuildDoc}
except ImportError:
    print "Sphinx not installed--needed to build documentation"
    # default cmdclass to None to avoid 
    cmdclass = {}
    
import django_assets


def find_packages(root):
    # so we don't depend on setuptools; from the Storm ORM setup.py
    packages = []
    for directory, subdirectories, files in os.walk(root):
        if '__init__.py' in files:
            packages.append(directory.replace(os.sep, '.'))
    return packages


setup(
    name = 'django-assets',
    version=".".join(map(str, django_assets.__version__)),
    description = 'Media asset management for the Django web framework.',
    long_description = 'Merges, minifies and compresses Javascript and '
        'CSS files, supporting a variety of different filters, including '
        'YUI, jsmin, jspacker or CSS tidy. Also supports URL rewriting '
        'in CSS files.',
    author = 'Michael Elsdoerfer',
    author_email = 'michael@elsdoerfer.info',
    license = 'BSD',
    url = 'http://launchpad.net/django-assets',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
        ],
    packages = find_packages('django_assets'),
    cmdclass=cmdclass,
)
