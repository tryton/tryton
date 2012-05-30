#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Lot Management',
    'name_es_ES': 'Gestión de lotes de stock',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Stock Lot Management''',
    'description_es_ES': '''Gestión de lotes de stock''',
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
        'locale/es_ES.po',
    ],
}
