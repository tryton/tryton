#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Stock Continental',
    'name_de_DE': 'Buchhaltung Lagerbewertung Kontinentale Methode',
    'version': '1.9.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add continental stock accounting for real-time stock valuation.
''',
    'description_de_DE': '''
    - Fügt die kontinentale Methode der Lagerbewertung in Echt-Zeit hinzu.
''',
    'depends': [
        'ir',
        'res',
        'account',
        'account_product',
        'stock',
    ],
    'xml': [
        'product.xml',
        'account.xml',
    ],
    'translation': [
        'de_DE.csv',
    ],
}
