#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Supply Production',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Supply Stock with Production''',
    'depends': [
        'ir',
        'product',
        'stock',
        'production',
        'stock_supply',
        ],
    'xml': [
        'production.xml',
        ],
    'translation': [
        ]
}
