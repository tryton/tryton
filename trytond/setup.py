#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from setuptools import setup, find_packages
import os

execfile(os.path.join('trytond', 'version.py'))


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(name=PACKAGE,
    version=VERSION,
    description='Tryton server',
    long_description=read('README'),
    author='Tryton',
    url=WEBSITE,
    download_url=("http://downloads.tryton.org/" +
        VERSION.rsplit('.', 1)[0] + '/'),
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
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        ],
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
        'timezone': ['pytz'],
        'simplejson': ['simplejson'],
        'cdecimal': ['cdecimal'],
        'Levenshtein': ['python-Levenshtein'],
        },
    zip_safe=False,
    test_suite='trytond.tests',
    test_loader='trytond.test_loader:Loader',
)
