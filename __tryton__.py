#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Sale',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define price list on party and sale order.
''',
    'depends': [
        'ir',
        'party',
        'product_price_list',
        'sale',
        'product',
    ],
    'xml': [
        'party.xml',
        'sale.xml',
    ],
    'translation': [
    ],
}
