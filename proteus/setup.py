#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import io
import os
import re

from setuptools import find_packages, setup


def read(fname):
    return io.open(
        os.path.join(os.path.dirname(__file__), fname),
        'r', encoding='utf-8').read()


def readme():
    content = read('README.rst')
    content = re.sub(
        r'(?m)^\.\. toctree::\r?\n((^$|^\s.*$)\r?\n)*', '', content)
    return content


def get_version():
    init = read(os.path.join('proteus', '__init__.py'))
    return re.search('__version__ = "([0-9.]*)"', init).group(1)


def get_require_version(name):
    require = '%s >= %s.%s, < %s.%s'
    require %= (name, major_version, minor_version,
        major_version, minor_version + 1)
    return require


name = 'proteus'
version = get_version()
major_version, minor_version, _ = version.split('.', 2)
major_version = int(major_version)
minor_version = int(minor_version)

if minor_version % 2:
    download_url = ''
else:
    download_url = 'http://downloads.tryton.org/%s.%s/' % (
        major_version, minor_version)

setup(name=name,
    version=version,
    description='Library to access Tryton server as a client',
    long_description=readme(),
    author='Tryton',
    author_email='foundation@tryton.org',
    url='http://www.tryton.org/',
    download_url=download_url,
    project_urls={
        "Bug Tracker": 'https://bugs.tryton.org/',
        "Documentation": 'https://docs.tryton.org/latest/client-library/',
        "Forum": 'https://www.tryton.org/forum',
        "Source Code": 'https://code.tryton.org/tryton',
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
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Office/Business',
        ],
    platforms='any',
    license='LGPL-3',
    python_requires='>=3.9',
    install_requires=[
        'defusedxml',
        "python-dateutil",
        ],
    extras_require={
        'trytond': [get_require_version('trytond')],
        'test': [
            get_require_version('trytond'),
            get_require_version('trytond_party'),
            ],
        },
    zip_safe=True,
    )
