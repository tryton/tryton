#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Stock Anglo-Saxon',
    'name_de_DE': 'Buchhaltung Lagerbewertung Angelsächsische Methode',
    'name_fr_FR': 'Gestion de stock anglo-saxonne',
    'version': '2.0.2',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add anglo-saxon stock accounting for real-time stock valuation.
''',
    'description_de_DE': '''
    - Fügt die angelsächsische Methode der Lagerbewertung in Echt-Zeit hinzu.
''',
    'description_fr_FR': '''
    Ajoute la gestion de stock anglo-saxonne pour une évaluation en temps réel de la valeur du stock
''',
    'depends': [
        'ir',
        'res',
        'account',
        'account_invoice',
        'account_product',
        'account_stock_continental',
        'purchase',
        'sale',
    ],
    'xml': [
        'product.xml',
        'account.xml',
    ],
    'translation': [
        'de_DE.csv',
        'fr_FR.csv',
    ],
}
