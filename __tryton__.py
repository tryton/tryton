#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Sale Pricelist',
    'name_de_DE': 'Verkauf Preislisten',
    'name_es_CO': 'Lista de Precios de Venta',
    'name_fr_FR' : 'Listes de prix de vente',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define price list on party and sale order.
''',
    'description_de_DE': '''Preislisten für Verkauf
    - Ermöglicht die Definition von Preislisten per Partei und Verkauf.
''',
    'description_es_CO': '''Precios de Venta
    - Define lista de precio de venta para un tercero y una orden de venta.
''',
    'description_fr_FR': '''Ajoute des listes de prix sur les tiers et sur les ventes.
''',
    'depends': [
        'ir',
        'party',
        'product_price_list',
        'sale',
    ],
    'xml': [
        'party.xml',
        'sale.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
    ],
}
