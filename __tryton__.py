#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Account',
    'name_de_DE': 'Kostenstellen',
    'name_fr_FR': 'Comptabilité analytique',
    'name_es_ES': 'Contabilidad Analítica',
    'version': '1.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Financial and Accounting Module with:
    - Analytic accounting with any number of analytic charts

And with report:
    - Analytic account balance
''',
    'description_de_DE': '''Modul für Buchhhaltung mit:
    - Kostenstellen mit einer beliebigen Anzahl von Tabellen

Zugehörige Berichte:
    - Plan für Kostenstellen
''',
    'description_fr_FR': '''Module comptable et financier, avec:
    - Comptabilité analytique autorisant un nombre arbitraire d'axes.

Et le rapport:
    - Balance comptable analytique
''',
    'description_es_ES': '''Módulo Financiero y de Contabilidad con:
    - Contabilidad Analítica con cualquier cantidad de planes analíticos

Y con reportes:
    - Balance Contable Analítico
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
