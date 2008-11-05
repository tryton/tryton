#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Sale',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Sale',
    'description': '''Define sale order.
Add to product sale informations.
Define the sale price as the list price.

With the possibilities:
    - to follow invoice and packing states from the sale order.
    - to define invoice method:
        - Manual
        - On Order Confirmed
        - On packing Sent
    - to define packing method:
        - Manual
        - On Order Confirmed
        - On Invoice Paid
''',
    'depends': [
        'company',
        'party',
        'stock',
        'account',
        'product',
        'account_invoice',
        'workflow',
        'res',
        'ir',
        'currency',
        'account_product',
    ],
    'xml': [
        'sale.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
