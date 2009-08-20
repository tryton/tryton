#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Price List',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define price list rules by parties.''',
    'depends': [
        'ir',
        'product',
        'party',
        'company',
    ],
    'xml': [
        'price_list.xml',
        'party.xml',
    ],
    'translation': [
    ],
}
