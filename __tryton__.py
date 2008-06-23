#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Purchase',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Purchase',
    'description': 'Analytic Purchase',
    'depends': [
        'purchase',
        'analytic_account',
        'analytic_invoice',
    ],
    'xml': [
        'purchase.xml',
    ],
}
