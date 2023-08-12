# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os

base_url = os.environ.get('DOC_BASE_URL')
if base_url:
    modules_url = base_url + '/modules-{module}/'
    trytond_url = base_url + '/server/'
else:
    modules_url = (
        'https://docs.tryton.org/projects/modules-{module}/en/{series}/')
    trytond_url = 'https://docs.tryton.org/projects/server/en/{series}/'


def get_info():
    import configparser
    import subprocess
    import sys

    module_dir = os.path.dirname(os.path.dirname(__file__))

    config = configparser.ConfigParser()
    config.read_file(open(os.path.join(module_dir, 'tryton.cfg')))
    info = dict(config.items('tryton'))

    result = subprocess.run(
        [sys.executable, 'setup.py', '--name'],
        stdout=subprocess.PIPE, check=True, cwd=module_dir)
    info['name'] = result.stdout.decode('utf-8').strip()

    result = subprocess.run(
        [sys.executable, 'setup.py', '--version'],
        stdout=subprocess.PIPE, check=True, cwd=module_dir)
    version = result.stdout.decode('utf-8').strip()
    major_version, minor_version, _ = version.split('.', 2)
    major_version = int(major_version)
    minor_version = int(minor_version)
    if minor_version % 2:
        info['series'] = 'latest'
    else:
        info['series'] = '.'.join(version.split('.', 2)[:2])

    for key in {'depends', 'extras_depend'}:
        info[key] = info.get(key, '').strip().splitlines()
    info['modules'] = set(info['depends'] + info['extras_depend'])
    info['modules'] -= {'ir', 'res'}

    return info


info = get_info()

master_doc = 'index'
project = info['name']
release = version = info['series']
default_role = 'ref'
highlight_language = 'none'
extensions = [
    'sphinx.ext.intersphinx',
    ]
intersphinx_mapping = {
    'trytond': (trytond_url.format(series=version), None),
    }
intersphinx_mapping.update({
        m: (modules_url.format(
                module=m.replace('_', '-'), series=version), None)
        for m in info['modules']
        })
linkcheck_ignore = [r'/.*', r'https://demo.tryton.org/*']

del get_info, info, base_url, modules_url, trytond_url
