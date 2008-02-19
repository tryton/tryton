#!/usr/bin/env python

from distutils.core import setup

info = eval(file('__tryton__.py').read())

requires = ['trytond'] + ['trytond-' + x for x in info.get('depends', [])]

setup(name='trytond-' + info['name'],
    version=info.get('version', '0'),
    description=info.get('description', ''),
    author=info.get('author', ''),
    author_email=info.get('email', ''),
    url=info.get('website', ''),
    package_dir={'trytond.modules.' + info['name']: ''},
    packages=[
        'trytond.modules.' + info['name'],
    ],
    package_data={
        'trytond.modules.' + info['name']: [' ' + x for x in info.get('xml', [])],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Plugins',
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'Intended Audience :: Legal Industry',
        'Intended Audience :: Manufacturing',
        'Natural Language :: English',
        'Natural Language :: French',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Office/Business',
    ],
    license=info.get('license', 'GPL-2'),
    #requires=requires,
)
