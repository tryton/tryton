#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Price List',
    'name_de_DE' : 'Artikel Preisliste',
    'name_fr_FR' : 'Liste de prix produit',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define price list rules by parties.''',
    'description_de_DE' : '''Preislisten für Artikel
    - Ermöglicht die Definition von Preislisten für Parteien.
''',
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
        'fr_FR.csv',
        'de_DE.csv',
    ],
}
