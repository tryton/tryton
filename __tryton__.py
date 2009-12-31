#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Dashboard',
    'name_de_DE': 'Dashboard',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Dashboard''',
    'description_de_DE': '''Dashboard:
    - Ermöglicht die Einrichtung einer personalisierten Startseite.
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
    ],
}
