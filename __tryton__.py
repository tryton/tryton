#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Sale',
    'name_de_DE': 'Kostenstellen Verkauf',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add analytic account on sale lines.
''',
    'description_de_DE': '''Fügt Kostenstellen zu den Verkaufspositionen hinzu
''',
    'depends': [
        'sale',
        'analytic_account',
        'analytic_invoice',
    ],
    'xml': [
        'sale.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
