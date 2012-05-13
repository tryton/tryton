#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Lot Management',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Stock Lot Management''',
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
    ],
}
