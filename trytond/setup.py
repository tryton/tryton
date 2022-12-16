#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from setuptools import setup, find_packages
import os
import sys

execfile(os.path.join('trytond', 'version.py'))

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(name=PACKAGE,
    version=VERSION,
    description='Tryton server',
    long_description=read('README'),
    author='B2CK',
    author_email='info@b2ck.com',
    url=WEBSITE,
    download_url="http://downloads.tryton.org/" + \
            VERSION.rsplit('.', 1)[0] + '/',
    packages=find_packages(exclude=['*.modules.*', 'modules.*', 'modules']),
    package_data={
        'trytond': ['ir/ui/icons/*.svg'],
        'trytond.backend.mysql': ['init.sql'],
        'trytond.backend.postgresql': ['init.sql'],
        'trytond.backend.sqlite': ['init.sql'],
        'trytond.ir': ['*.xml', 'locale/*.po'],
        'trytond.ir.module': ['*.xml'],
        'trytond.ir.ui': ['*.xml', '*.rng', '*.rnc'],
        'trytond.res': ['*.xml', 'locale/*.po'],
        'trytond.webdav': ['*.xml', 'locale/*.po'],
        'trytond.workflow': ['*.xml', 'locale/*.po'],
        'trytond.test': ['*.xml'],
    },
    scripts=['bin/trytond'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Framework :: Tryton',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: Bulgarian',
        'Natural Language :: Czech',
        'Natural Language :: Dutch',
        'Natural Language :: English',
        'Natural Language :: French',
        'Natural Language :: German',
        'Natural Language :: Russian',
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
    ],
    extras_require={
        'PostgreSQL': ['psycopg2 >= 2.0'],
        'MySQL': ['MySQL-python'],
        'WebDAV': ['PyWebDAV >= 0.9.3'],
        'unoconv': ['unoconv'],
        'SSL': ['pyOpenSSL'],
        'graphviz': ['pydot'],
        'timezone': ['pytz'],
        'simplejson': ['simplejson'],
    },
    zip_safe=False,
    test_suite='trytond.tests',
    test_loader='trytond.test_loader:Loader',
)
