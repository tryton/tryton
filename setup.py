#!/usr/bin/env python

from distutils.core import setup
from distutils.command import sdist


class mysdist(sdist.sdist):

    def add_defaults(self):
        sdist.sdist.add_defaults(self)
        if self.distribution.has_pure_modules():
            build_py = self.get_finalized_command('build_py')
            data = []
            for package in build_py.packages:
                src_dir = build_py.get_package_dir(package)
                data.extend(build_py.find_data_files(package, src_dir))
            self.filelist.extend(data)

info = eval(file('__tryton__.py').read())

requires = ['trytond'] + ['trytond-' + x for x in info.get('depends', [])]

setup(name='trytond-' + info['name'].lower(),
    version=info.get('version', '0'),
    description=info.get('description', ''),
    author=info.get('author', ''),
    author_email=info.get('email', ''),
    url=info.get('website', ''),
    package_dir={'trytond.modules.' + info['name'].lower(): '.'},
    packages=[
        'trytond.modules.' + info['name'].lower(),
    ],
    package_data={
        'trytond.modules.' + info['name'].lower(): info.get('xml', []),
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Plugins',
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'Intended Audience :: Legal Industry',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Office/Business',
    ],
    license=info.get('license', 'GPL-2'),
    #requires=requires,
    cmdclass={
        'sdist': mysdist,
    },
)
