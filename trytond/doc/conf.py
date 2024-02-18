# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os

base_url = os.environ.get('DOC_BASE_URL')
if base_url:
    modules_url = base_url + '/modules-{module}/'
    tryton_url = base_url + '/client-desktop/'
    proteus_url = base_url + '/client-library/'
else:
    modules_url = 'https://docs.tryton.org/${series}/modules-{module}/'
    tryton_url = 'https://docs.tryton.org/${series}/client-desktop/'
    proteus_url = 'https://docs.tryton.org/${series}/client-library/'


def get_info():
    import subprocess
    import sys

    module_dir = os.path.dirname(os.path.dirname(__file__))

    info = dict()

    result = subprocess.run(
        [sys.executable, 'setup.py', '--name', '--description'],
        stdout=subprocess.PIPE, check=True, cwd=module_dir)
    info['name'], info['description'] = (
        result.stdout.decode('utf-8').strip().splitlines())

    result = subprocess.run(
        [sys.executable, 'setup.py', '--version'],
        stdout=subprocess.PIPE, check=True, cwd=module_dir)
    version = result.stdout.decode('utf-8').strip()
    major_version, minor_version, _ = version.split('.', 2)
    major_version = int(major_version)
    minor_version = int(minor_version)
    if minor_version % 2:
        info['series'] = 'latest'
        info['branch'] = 'branch/default'
    else:
        info['series'] = '.'.join(version.split('.', 2)[:2])
        info['branch'] = 'branch/' + info['series']

    return info


info = get_info()

html_theme = 'sphinx_book_theme'
html_theme_options = {
    'repository_provider': 'gitlab',
    'repository_url': 'https://code.tryton.org/tryton',
    'repository_branch': info['branch'],
    'use_source_button': True,
    'use_edit_page_button': True,
    'use_repository_button': True,
    'use_download_button': False,
    'path_to_docs': 'trytond/doc',
    }
html_title = info['description']
master_doc = 'index'
project = info['name']
release = version = info['series']
default_role = 'ref'
highlight_language = 'none'
extensions = [
    'sphinx_copybutton',
    'sphinx.ext.intersphinx',
    ]
intersphinx_mapping = {
    'python': ('https://docs.python.org/', None),
    }
linkcheck_ignore = [r'/.*', r'https://demo.tryton.org/*']

del get_info, info, base_url, modules_url, tryton_url, proteus_url
