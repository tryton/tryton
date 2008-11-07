#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project',
    'name_de_DE': 'Projekte',
    'name_fr_FR': 'Projet',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Project Module with:
    - Project management
''',
    'description_de_DE': '''Projektmodul für:
    - Projektverwaltung
''',
    'description_fr_FR': '''Module projet avec:
    - Gestion de projet
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
