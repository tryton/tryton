#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
{
    'name': 'Company',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Generic',
    'description': 'Define company',
    'depends': [
        'ir',
        'res',
        'relationship',
        'currency',
    ],
    'xml': [
        'company.xml',
    ],
    'translation': [
        'fr_FR.csv',
    ]
}
