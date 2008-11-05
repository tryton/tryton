#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Product',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': '''Add accounting properties on product and category like:
    - account for expense / revenue
    - taxes for customer / supplier
''',
    'depends': [
        'ir',
        'account',
        'company',
        'product',
    ],
    'xml': [
        'product.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ]
}
