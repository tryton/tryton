#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Sale',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Sale',
    'description': 'Sale Management',
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
    ],
    'xml': [
        'sale.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
