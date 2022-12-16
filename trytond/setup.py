#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from setuptools import setup, find_packages
import os
import sys

execfile(os.path.join('trytond', 'version.py'))

SIMPLEJSON = []
if sys.version_info < (2, 6):
    SIMPLEJSON = ['simplejson']

setup(name=PACKAGE,
    version=VERSION,
    description='Tryton server',
    author='B2CK',
    author_email='info@b2ck.com',
    url=WEBSITE,
    download_url="http://downloads.tryton.org/" + \
            VERSION.rsplit('.', 1)[0] + '/',
    packages=find_packages(exclude=['*.modules.*', 'modules.*', 'modules']),
    package_data={
        'trytond.backend.mysql': ['init.sql'],
        'trytond.backend.postgresql': ['init.sql'],
        'trytond.backend.sqlite': ['init.sql'],
        'trytond.ir': ['*.xml', '*.csv'],
        'trytond.ir.module': ['*.xml'],
        'trytond.ir.ui': ['*.xml', '*.rng', '*.rnc'],
        'trytond.res': ['*.xml', '*.csv'],
        'trytond.webdav': ['*.xml', '*.csv'],
        'trytond.workflow': ['*.xml', '*.csv'],
        'trytond.test': ['*.xml'],
    },
    scripts=['bin/trytond'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Natural Language :: French',
        'Natural Language :: German',
        'Natural Language :: Russian',
        'Natural Language :: Spanish',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
    ],
    license=LICENSE,
    install_requires=[
        'lxml >= 2.0',
        'relatorio >= 0.2.0',
        'Genshi',
        'python-dateutil',
    ] + SIMPLEJSON,
    extras_require={
        'PostgreSQL': ['psycopg2 >= 2.0'],
        'MySQL': ['MySQL-python'],
        'WebDAV': ['PyWebDAV >= 0.9.3'],
        'PDF': ['openoffice-python'],
        'SSL': ['pyOpenSSL'],
        'graphviz': ['pydot'],
        'timezone': ['pytz'],
    },
    zip_safe=False,
    test_suite='trytond.tests',
    test_loader='trytond.test_loader:Loader',
)
