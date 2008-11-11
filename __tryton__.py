#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Forecast',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Stock Forecast.
Allow to generate future moves which will enable other process to anticipate them.
''',

    'depends': [
        'ir',
        'res',
        'workflow',
        'stock',
        'product',
        'company',
    ],
    'xml': [
        'forecast.xml',
    ],
    'translation': [
    ],
}
