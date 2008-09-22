#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
{
    'name': 'Project Revenue',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Project',
    'description': 'Project Revenue Module',
    'depends': [
        'ir',
        'project',
        'company',
        'product',
    ],
    'xml': [
        'service.xml',
        'timesheet.xml',
    ],
    'translation': [
        'de_DE.csv',
    ],
}
