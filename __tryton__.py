#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Price List',
    'name_de_DE' : 'Artikel Preisliste',
    'name_es_CO': 'Lista de precios de producto',
    'name_es_ES': 'Lista de precios de producto',
    'name_fr_FR' : 'Liste de prix produit',
    'version': '1.8.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define price list rules by parties.''',
    'description_de_DE' : '''Preislisten für Artikel
    - Ermöglicht die Definition von Preislisten für Parteien.
''',
    'description_es_CO': 'Define reglas de lista de precios por tercero.',
    'description_es_ES': 'Define reglas de lista de precios por tercero.',
    'description_fr_FR' : '''Défini des listes de prix par tiers''',
    'depends': [
        'ir',
        'product',
        'party',
        'company',
    ],
    'xml': [
        'price_list.xml',
        'party.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
