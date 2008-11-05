#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Purchase',
    'name_de_DE': 'Kostenstellen Einkauf',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Purchase',
    'description': '''Add analytic account on purchase lines.
''',
    'description_de_DE': '''Fügt kostenstellen zu Einkaufspositionen hinzu
''',
    'depends': [
        'purchase',
        'analytic_account',
        'analytic_invoice',
    ],
    'xml': [
        'purchase.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
