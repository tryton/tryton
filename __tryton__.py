#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project Revenue',
    'name_de_DE': 'Projekte Ertrag',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Project',
    'description': '''Add product on timesheet lines.
Define allowed service for each employees.
''',
    'description_de_DE': ''' - Ermöglicht das Hinzufügen von Artikeln zu Zeitpositionen.
 - Ermöglicht die Definition von Dienstleistungen, die für einen Mitarbeiter verwendet werden können.
''',
    'depends': [
        'ir',
        'project',
        'company',
        'product',
    ],
    'xml': [
        'service.xml',
        'timesheet.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
