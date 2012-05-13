#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Production Management',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Production Management with:
    - Bill of Material
    - Production Order
    ''',
    'depends': [
        'ir',
        'res',
        'product',
        'company',
        'stock',
    ],
    'xml': [
        'production.xml',
        'configuration.xml',
        'bom.xml',
        'product.xml',
        'stock.xml',
    ],
    'translation': [
    ]
}
