#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Statement',
    'name_de_DE': 'Buchhaltung Bankauszüge',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': 'Account Statement Module',
    'description_de_DE': '''Modul für Buchhaltung und Bankauszüge mit
    - Abstimmung von Bankauszügen und Rechnungen
''',
    'depends': [
        'account',
        'company',
        'currency',
        'party',
        ],
    'xml': [
        'statement.xml',
        'journal.xml',
        ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
