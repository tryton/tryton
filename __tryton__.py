#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Account',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': 'Financial and Accounting Module',
    'depends': [
        'ir',
        'company',
        'currency',
        'account',
        'party',
        'res',
    ],
    'xml': [
        'analytic_account.xml',
        'account.xml',
        'line.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
