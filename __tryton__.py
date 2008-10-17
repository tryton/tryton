#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Supply Management',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Inventory',
    'description': 'Supply Management Module',
    'depends': [
        'ir',
        'res',
        'product',
        'stock',
        'purchase',
    ],
    'xml': [
        'order_point.xml',
        'purchase_request.xml',
        'packing.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ]
}
