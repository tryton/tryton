#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Management',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Inventory',
    'description': 'Stock Management and Inventory Control',
    'depends': [
        'ir',
        'workflow',
        'party',
        'product',
        'company',
        'currency',
    ],
    'xml': [
        'stock.xml',
        'product.xml',
        'location.xml',
        'packing.xml',
        'move.xml',
        'inventory.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
