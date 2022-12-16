#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Res',
    'name_de_DE': 'Benutzerverwaltung',
    'description': '''Basic module handling internal tasks of the application.
Provides concepts and administration of users and internal communication.
''',
    'description_de_DE': '''Basismodul für interne Aufgaben der Anwendung

 - Stellt Konzept und Administration für die Benutzerverwaltung und interne Kommunikation zur Verfügung
''',
    'active': True,
    'depends': ['ir'],
    'xml': [
        'res.xml',
        'group.xml',
        'user.xml',
        'request.xml',
        'ir.xml',
        ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
        'es_CO.csv',
    ],
}
