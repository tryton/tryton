#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from setuptools import setup, find_packages
import os
import re
import io
import platform


def read(fname):
    return io.open(
        os.path.join(os.path.dirname(__file__), fname),
        'r', encoding='utf-8').read()


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
    pg_require = ['psycopg2cffi >= 2.5.4']
else:
    pg_require = ['psycopg2 >= 2.5.4']

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
        'trytond.backend.postgresql': ['init.sql'],
        'trytond.backend.sqlite': ['init.sql'],
        'trytond.ir': ['tryton.cfg', '*.xml', 'view/*.xml', 'locale/*.po'],
        'trytond.ir.module': ['*.xml'],
        'trytond.ir.ui': ['*.xml', '*.rng', '*.rnc'],
        'trytond.res': [
            'tryton.cfg', '*.xml', '*.html', 'view/*.xml', 'locale/*.po'],
        'trytond.tests': ['tryton.cfg', '*.xml', 'forbidden.txt'],
        },
    scripts=[
        'bin/trytond',
        'bin/trytond-admin',
        'bin/trytond-cron',
        'bin/trytond-worker',
        ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Framework :: Tryton',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Natural Language :: Bulgarian',
        'Natural Language :: Catalan',
        'Natural Language :: Chinese (Simplified)',
        'Natural Language :: Czech',
        'Natural Language :: Dutch',
        'Natural Language :: English',
        'Natural Language :: French',
        'Natural Language :: German',
        'Natural Language :: Hungarian',
        'Natural Language :: Italian',
        'Natural Language :: Persian',
        'Natural Language :: Polish',
        'Natural Language :: Portuguese (Brazilian)',
        'Natural Language :: Russian',
        'Natural Language :: Slovenian',
        'Natural Language :: Spanish',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        ],
    platforms='any',
    license='GPL-3',
    python_requires='>=3.4',
    install_requires=[
        'lxml >= 2.0; python_version != "3.4"',
        'lxml >=2.0, < 4.4; python_version == "3.4"',
        'relatorio[fodt] >= 0.7.0',
        'Genshi',
        'python-dateutil',
        'polib',
        'python-sql >= 0.5',
        'werkzeug < 1.0',
        'wrapt',
        'passlib >= 1.7.0',
        ],
    extras_require={
        'PostgreSQL': pg_require,
        'graphviz': ['pydot'],
        'Levenshtein': ['python-Levenshtein'],
        'BCrypt': ['passlib[bcrypt]'],
        'html2text': ['html2text'],
        },
    zip_safe=False,
    test_suite='trytond.tests',
    test_loader='trytond.test_loader:Loader',
    )
