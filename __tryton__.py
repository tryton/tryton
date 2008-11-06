#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Account',
    'name_de_DE': 'Kostenstellen',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': '''Financial and Accounting Module with:
    - Analytic accounting with any number of analytic charts

And with reports:
    - Analytic account balance
''',
    'description_de_DE': '''Modul für Buchhhaltung mit:
    - Kostenstellen mit einer beliebigen Anzahl von Tabellen

Zugehörige Berichte:
    - Plan für Kostenstellen
''',
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
        'fr_FR.csv',
    ],
}
