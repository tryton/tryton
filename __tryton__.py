#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Invoice',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': 'Analytic Invoice',
    'depends': [
        'account_invoice',
        'analytic_account',
    ],
    'xml': [
        'invoice.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
