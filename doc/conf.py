# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os

base_url = os.environ.get('DOC_BASE_URL')
if base_url:
    modules_url = base_url + '/modules-{module}/'
    trytond_url = base_url + '/server/'
    trytond_gis_url = base_url + '/backend-gis/'
    tryton_url = base_url + '/client-desktop/'
    proteus_url = base_url + '/client-library/'
else:
    modules_url = (
        'https://docs.tryton.org/${series}/modules-{module}/')
    trytond_url = 'https://docs.tryton.org/${series}/server/'
    trytond_gis_url = 'https://docs.tryton.org/${series}/backend-gis/'
    tryton_url = 'https://docs.tryton.org/${series}/client-desktop/'
    proteus_url = 'https://docs.tryton.org/${series}/client-library/'


def get_info():
    import subprocess
    import sys

    trytond_dir = os.path.join(os.path.dirname(__file__), '../trytond')

    info = dict()

    result = subprocess.run(
        [sys.executable, 'setup.py', '--version'],
        stdout=subprocess.PIPE, check=True, cwd=trytond_dir)
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

    info['modules'] = [
         e.name for e in os.scandir('../modules') if e.is_dir()]

    return info


info = get_info()

html_theme = 'sphinx_book_theme'
html_theme_options = {
    'logo': {
        'alt_text': "Tryton Documentation",
        'image_light': 'https://docs.tryton.org/logo-light.svg',
        'image_dark': 'https://docs.tryton.org/logo-dark.svg',
        'link': base_url,
        },
    'home_page_in_toc': True,
    'repository_provider': 'gitlab',
    'repository_url': 'https://code.tryton.org/tryton',
    'repository_branch': info['branch'],
    'use_source_button': True,
    'use_edit_page_button': True,
    'use_repository_button': True,
    'use_download_button': False,
    'path_to_docs': 'doc',
    }
html_title = "Tryton Documentation"
master_doc = 'index'
project = "Tryton Documentation"
release = version = info['series']
default_role = 'ref'
highlight_language = 'none'
extensions = [
    'sphinx_copybutton',
    'sphinx.ext.intersphinx',
    ]
intersphinx_mapping = {
    'python': ('https://docs.python.org/', None),
    'trytond': (trytond_url.format(series=version), None),
    'trytond_gis': (trytond_gis_url.format(series=version), None),
    'tryton': (tryton_url.format(series=version), None),
    'proteus': (proteus_url.format(series=version), None),
    }
intersphinx_mapping.update({
        m: (modules_url.format(
                module=m.replace('_', '-'), series=version), None)
        for m in info['modules']
        })
linkcheck_ignore = [r'/.*', r'https://demo.tryton.org/*']
del (
    get_info, info, base_url, modules_url, trytond_url, trytond_gis_url,
    tryton_url, proteus_url)
