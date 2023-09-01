# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

html_theme = 'sphinx_book_theme'
html_theme_options = {
    'repository_provider': 'gitlab',
    'repository_url': 'https://code.tryton.org/tryton',
    'repository_branch': 'branch/default',
    'use_source_button': True,
    'use_edit_page_button': True,
    'use_repository_button': True,
    'use_download_button': False,
    'path_to_docs': 'readthedocs',
    }
html_title = "Tryton Documentation"
master_doc = 'index'
project = "Tryton Documentation"
default_role = 'ref'
highlight_language = 'none'
extensions = [
    'sphinx_copybutton',
    ]
linkcheck_ignore = [r'/.*', r'https://demo.tryton.org/*']
