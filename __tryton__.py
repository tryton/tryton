#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Currency',
    'name_de_DE': 'Währung',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Generic',
    'description': '''Define currencies and exchange rate.
Allow to customize the formatting of the currency amount.
''',
    'description_de_DE': ''' - Ermöglicht die Eingabe von Währungen und Wechselkursen.
 - Erlaubt die beliebige Formatierung von Währungsbeträgen.
''',
    'depends': [
        'ir',
        'res',
    ],
    'xml': [
        'currency.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ]
}
