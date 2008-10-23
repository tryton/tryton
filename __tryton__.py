#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Invoice',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': 'Invoice',
    'depends': [
        'ir',
        'account',
        'company',
        'party',
        'product',
        'res',
        'workflow',
        'currency',
    ],
    'xml': [
        'invoice.xml',
        'product.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ]
}
