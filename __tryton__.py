#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project',
    'name_de_DE': 'Projekte',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Project',
    'description': '''Project Module with:
    - Project management
''',
    'description_de_DE': '''Projektmodul für:
    - Projektverwaltung
''',
    'depends': [
        'ir',
        'timesheet',
        'party',
    ],
    'xml': [
        'project.xml',
        'work.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
