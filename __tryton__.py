#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Lot Management',
    'name_de_DE': 'Lager Chargenverwaltung',
    'name_es_ES': 'Gestión de lotes de stock',
    'name_fr_FR': 'Gestion des lots de stock',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Stock Lot Management''',
    'description_de_DE': '''Verwaltung von Chargen im Lager''',
    'description_es_ES': '''Gestión de lotes de stock''',
    'description_fr_FR': '''Gestion des lots de stock.''',
    'depends': [
        'ir',
        'product',
        'stock',
    ],
    'xml': [
        'stock.xml',
        'product.xml',
    ],
    'translation': [
        'locale/de_DE.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
    ],
}
