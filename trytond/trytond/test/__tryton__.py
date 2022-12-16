#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Test',
    'description': '''A module for unittest.
''',
    'active': True,
    'depends': ['ir', 'res', 'workflow'],
    'xml': [
        'import_data.xml',
        'sequence.xml',
        'workflow.xml',
    ],
    'translation': [
    ],
}
