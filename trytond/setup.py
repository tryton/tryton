#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from setuptools import setup, find_packages
import os

PACKAGE, VERSION, LICENSE, WEBSITE = None, None, None, None
execfile(os.path.join('trytond', 'version.py'))


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

major_version, minor_version, _ = VERSION.split('.', 2)
major_version = int(major_version)
minor_version = int(minor_version)

download_url = 'http://downloads.tryton.org/%s.%s/' % (
    major_version, minor_version)
if minor_version % 2:
    VERSION = '%s.%s.dev0' % (major_version, minor_version)
    download_url = 'hg+http://hg.tryton.org/%s#egg=%s-%s' % (
        PACKAGE, PACKAGE, VERSION)

setup(name=PACKAGE,
    version=VERSION,
    description='Tryton server',
    long_description=read('README'),
    author='Tryton',
    author_email='issue_tracker@tryton.org',
    url=WEBSITE,
    download_url=download_url,
    keywords='business application platform ERP',
    packages=find_packages(exclude=['*.modules.*', 'modules.*', 'modules',
            '*.proteus.*', 'proteus.*', 'proteus']),
    package_data={
        'trytond': ['ir/ui/icons/*.svg'],
        'trytond.backend.mysql': ['init.sql'],
        'trytond.backend.postgresql': ['init.sql'],
        'trytond.backend.sqlite': ['init.sql'],
        'trytond.ir': ['tryton.cfg', '*.xml', 'view/*.xml', 'locale/*.po'],
        'trytond.ir.module': ['*.xml'],
        'trytond.ir.ui': ['*.xml', '*.rng', '*.rnc'],
        'trytond.res': ['tryton.cfg', '*.xml', 'view/*.xml', 'locale/*.po'],
        'trytond.webdav': ['tryton.cfg', '*.xml', 'view/*.xml', 'locale/*.po'],
        'trytond.tests': ['tryton.cfg', '*.xml'],
        },
    scripts=['bin/trytond'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Framework :: Tryton',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: Bulgarian',
        'Natural Language :: Catalan',
        'Natural Language :: Czech',
        'Natural Language :: Dutch',
        'Natural Language :: English',
        'Natural Language :: French',
        'Natural Language :: German',
        'Natural Language :: Russian',
        'Natural Language :: Slovenian',
        'Natural Language :: Spanish',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        ],
    platforms='any',
    license=LICENSE,
    install_requires=[
        'lxml >= 2.0',
        'relatorio >= 0.2.0',
        'Genshi',
        'python-dateutil',
        'polib',
        'python-sql >= 0.2',
        ],
    extras_require={
        'PostgreSQL': ['psycopg2 >= 2.0'],
        'MySQL': ['MySQL-python'],
        'WebDAV': ['PyWebDAV >= 0.9.8'],
        'unoconv': ['unoconv'],
        'graphviz': ['pydot'],
        'simplejson': ['simplejson'],
        'cdecimal': ['cdecimal'],
        'Levenshtein': ['python-Levenshtein'],
        'BCrypt': ['bcrypt'],
        },
    zip_safe=False,
    test_suite='trytond.tests',
    test_loader='trytond.test_loader:Loader',
    tests_require=['mock'],
    )
