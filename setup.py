#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from setuptools import setup, find_packages
import re

info = eval(file('__tryton__.py').read())

requires = []
for dep in info.get('depends', []):
    match = re.compile(
            '(ir|res|workflow|webdav)((\s|$|<|>|<=|>=|==|!=).*?$)').match(dep)
    if match:
        continue
    else:
        dep = 'trytond_' + dep
    requires.append(dep)

major_version, minor_version, _ = info.get('version', '1.1.0').split('.', 2)
requires.append('trytond >= %s.%s' % (major_version, minor_version))
requires.append('trytond < %s.%s' % (major_version, str(int(minor_version) + 1)))

setup(name='trytond_account_de_skr03',
    version=info.get('version', '1.1.0'),
    description=info.get('description', ''),
    author=info.get('author', ''),
    author_email=info.get('email', ''),
    url=info.get('website', ''),
    long_description = "http://mercurial.intuxication.org/tryton/" + \
            "account_de_skr03/rev/2a04de0e5b75/",
    download_url="http://downloads.tryton.org/" + \
           info.get('version', '1.1.0').rsplit('.', 1)[0] + '/',
    package_dir={'trytond.modules.account_de_skr03': '.'},
    packages=[
        'trytond.modules.account_de_skr03',
    ],
    package_data={
        'trytond.modules.account_de_skr03': info.get('xml', []) \
                + info.get('translation', [])
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Plugins',
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'Intended Audience :: Legal Industry',
        'Intended Audience :: Manufacturing',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: German',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Office/Business :: Financial :: Accounting',
    ],
    license='GPL-3',
    install_requires=requires,
    zip_safe=False,
    entry_points="""
    [trytond.modules]
    account_de_skr03 = trytond.modules.account_de_skr03
    """,
)
