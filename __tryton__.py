#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Dashboard',
    'name_de_DE': 'Dashboard',
    'name_es_CO': 'Escritorio',
    'name_es_ES': 'Escritorio',
    'name_fr_FR': 'Tableau de bord',
    'version': '1.9.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Dashboard:
    - Allow to create a personalized dashboard.
''',
    'description_de_DE': '''Dashboard:
    - Ermöglicht die Einrichtung einer personalisierten Startseite.
''',
    'description_es_CO': '''Escritorio:
    - Permite la creación de una página de inicio personalizada.
''',
    'description_es_ES': '''Escritorio:
    - Permite la creación de una página de inicio personalizada.
''',
    'description_fr_FR': '''Tableau de bord
    - Permet de créer un tableau de bord personalisé.
''',
    'depends': [
        'ir',
        'res',
    ],
    'xml': [
        'dashboard.xml',
        'res.xml',
        'ir.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
