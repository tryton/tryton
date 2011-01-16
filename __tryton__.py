#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Stock Continental',
    'version': '1.9.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add continental stock accounting for real-time stock valuation.
''',
    'depends': [
        'ir',
        'res',
        'account',
        'account_product',
        'stock',
    ],
    'xml': [
        'product.xml',
        'account.xml',
    ],
    'translation': [
    ],
}
