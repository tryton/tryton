#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from setuptools import setup, find_packages
import os

execfile(os.path.join('trytond', 'version.py'))

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
        'trytond.backend.postgresql': ['init.sql'],
        'trytond.backend.sqlite': ['init.sql'],
        'trytond.ir': ['*.xml', '*.csv'],
        'trytond.ir.module': ['*.xml'],
        'trytond.ir.ui': ['*.xml', '*.rng', '*.rnc'],
        'trytond.res': ['*.xml', '*.csv'],
        'trytond.webdav': ['*.xml', '*.csv'],
        'trytond.workflow': ['*.xml', '*.csv'],
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
        'Natural Language :: Spanish',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
    ],
    license=LICENSE,
    install_requires=[
        'lxml',
        'egenix-mx-base',
        'relatorio >= 0.2.0',
        'Genshi',
    ],
    extras_require={
        'PostgreSQL': ['psycopg2 >= 2.0'],
        'WebDAV': ['PyWebDAV >= 0.9.3'],
        'PDF': ['openoffice.interact'],
        'SSL': ['pyOpenSSL'],
        'graphviz': ['pydot'],
        'timezone': ['pytz'],
    },
    zip_safe=False,
)
