#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'WebDAV',
    'name_de_DE': 'WebDAV',
    'description': '''Basic module providing concept and administration of integrated webDAV features.
''',
    'description_de_DE': '''Basismodul für Konzept und Administration der integrierten WebDAV-Komponente
''',
    'active': True,
    'depends': ['ir'],
    'xml': [
        'webdav.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
        'es_CO.csv',
    ],
}
