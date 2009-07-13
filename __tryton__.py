#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project Plan',
    'name_de_DE': 'Projekte Planung',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add planning capabilities on projects.
''',
    'description_de_DE': '''Projektmodul Planung:
    - Fügt Planungsmöglichkeiten für Projekte hinzu
''',
    'depends': [
        'ir',
        'company',
        'project',
        'timesheet',
    ],
    'xml': [
        'work.xml',
        'allocation.xml',
    ],
    'translation': [
        'de_DE.csv',
    ],
}
