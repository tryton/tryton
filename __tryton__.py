#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Supply Management',
    'name_de_DE': 'Lagerverwaltung Beschaffung',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Inventory',
    'description': '''Supply Management Module with:
    - Order point
    - Purchase Request

With scheduler:
    - to generate purchase request based on order points
    - to generate internal packing based on order points
''',
    'description_de_DE': '''Beschaffungsmodul mit:
    - Bestellpunkten
    - Auftragserstellung

Mit automatischer Auftragserstellung per Zeitplaner:
    - um Bestellungen auf der Basis von Bestellpunkten zu erstellen
    - um internen Versand auf der Basis von Bestellpunkten zu erstellen
''',
    'depends': [
        'ir',
        'res',
        'product',
        'stock',
        'purchase',
        'party',
    ],
    'xml': [
        'order_point.xml',
        'purchase_request.xml',
        'packing.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ]
}
