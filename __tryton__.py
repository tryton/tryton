#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Supply Forecast',
    'name_de_DE': 'Lagerverwaltung Bestellwesen Bedarfsermittlung',
    'name_fr_FR': 'Prévisions et approvisionnemenets de stock',
    'version': '2.2.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Take care of forecast when generating purchase requests.
''',
    'description_de_DE': '''Bestellwesen mit Bedarfsermittlung
    - Berücksichtigt die Vorhersagen der Bedarfsermittlung im Bestellwesen
''',
    'description_fr_FR': '''
Prend en compte les prévisions lors de la génération des demandes d'achat.
''',
    'depends': [
        'ir',
        'stock_supply',
        'stock_forecast',
    ],
    'xml': [
    ],
    'translation': [
    ],
}
