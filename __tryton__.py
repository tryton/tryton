#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Supply Forecast',
    'name_bg_BG': 'Управление прогноза доставка на наличност',
    'name_ca_ES': 'Previsió de proveïment d''estoc',
    'name_de_DE': 'Lagerverwaltung Bestellwesen Bedarfsermittlung',
    'name_es_AR': 'Previsión de abastecimiento de existencias',
    'name_es_ES': 'Previsión de abastecimiento de stock',
    'name_fr_FR': 'Prévisions et approvisionnemenets de stock',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Take care of forecast when generating purchase requests.
''',
    'description_ca_ES': '''Té en compte les previsions quan es generen
peticions de compra.
''',
    'description_de_DE': '''Bestellwesen mit Bedarfsermittlung
    - Berücksichtigt die Vorhersagen der Bedarfsermittlung im Bestellwesen
''',
    'description_es_AR': '''Toma en cuenta la previsión a la hora de generar
solicitudes de compra.
''',
    'description_es_ES': '''Toma en cuenta las previsiones a la hora de generar
solicitudes de compra.
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
