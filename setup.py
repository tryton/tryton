#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from setuptools import setup, find_packages
import os
import re
import platform


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


def get_version():
    init = read(os.path.join('trytond', '__init__.py'))
    return re.search('__version__ = "([0-9.]*)"', init).group(1)

version = get_version()
major_version, minor_version, _ = version.split('.', 2)
major_version = int(major_version)
minor_version = int(minor_version)
name = 'trytond'

download_url = 'http://downloads.tryton.org/%s.%s/' % (
    major_version, minor_version)
if minor_version % 2:
    version = '%s.%s.dev0' % (major_version, minor_version)
    download_url = 'hg+http://hg.tryton.org/%s#egg=%s-%s' % (
        name, name, version)

if platform.python_implementation() == 'PyPy':
    pg_require = ['psycopg2cffi >= 2.5']
else:
    pg_require = ['psycopg2 >= 2.0']

setup(name=name,
    version=version,
    description='Tryton server',
    long_description=read('README'),
    author='Tryton',
    author_email='issue_tracker@tryton.org',
    url='http://www.tryton.org/',
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
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        ],
    platforms='any',
    license='GPL-3',
    install_requires=[
        'lxml >= 2.0',
        'relatorio >= 0.2.0',
        'Genshi',
        'python-dateutil',
        'polib',
        'python-sql >= 0.4',
        ],
    extras_require={
        'PostgreSQL': pg_require,
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
