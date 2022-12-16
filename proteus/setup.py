#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import io
import os
import re
from setuptools import setup, find_packages


def read(fname):
    return io.open(
        os.path.join(os.path.dirname(__file__), fname),
        'r', encoding='utf-8').read()


def get_version():
    init = read(os.path.join('proteus', '__init__.py'))
    return re.search('__version__ = "([0-9.]*)"', init).group(1)


def get_require_version(name):
    if minor_version % 2:
        require = '%s >= %s.%s.dev0, < %s.%s'
    else:
        require = '%s >= %s.%s, < %s.%s'
    require %= (name, major_version, minor_version,
        major_version, minor_version + 1)
    return require


name = 'proteus'
version = get_version()
major_version, minor_version, _ = version.split('.', 2)
major_version = int(major_version)
minor_version = int(minor_version)

download_url = 'http://downloads.tryton.org/%s.%s/' % (
    major_version, minor_version)
if minor_version % 2:
    version = '%s.%s.dev0' % (major_version, minor_version)
    download_url = 'hg+http://hg.tryton.org/%s#egg=%s-%s' % (
        name, name, version)

dependency_links = []
if minor_version % 2:
    dependency_links.append('https://trydevpi.tryton.org/')

setup(name=name,
    version=version,
    description='Library to access Tryton server as a client',
    long_description=read('README.rst'),
    author='Tryton',
    author_email='bugs@tryton.org',
    url='http://www.tryton.org/',
    download_url=download_url,
    project_urls={
        "Bug Tracker": 'https://bugs.tryton.org/',
        "Documentation": 'https://docs.tryton.org/',
        "Forum": 'https://www.tryton.org/forum',
        "Source Code": 'https://hg.tryton.org/proteus',
        },
    keywords='tryton library cli',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Plugins',
        'Framework :: Tryton',
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'Intended Audience :: Legal Industry',
        'License :: OSI Approved :: '
        'GNU Library or Lesser General Public License (LGPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Office/Business',
        ],
    platforms='any',
    license='LGPL-3',
    python_requires='>=3.5',
    install_requires=[
        "python-dateutil",
        ],
    extras_require={
        'trytond': [get_require_version('trytond')],
        },
    dependency_links=dependency_links,
    zip_safe=True,
    test_suite='proteus.tests',
    tests_require=[get_require_version('trytond'),
        get_require_version('trytond_party')],
    )
