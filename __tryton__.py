#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Statement',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': 'Account Statement Module',
    'depends': [
        'account',
        'company',
        'currency',
        'relationship',
        ],
    'xml': [
        'statement.xml',
        'journal.xml',
        ],
    'translation': [
        'de_DE.csv',
    ],
}
