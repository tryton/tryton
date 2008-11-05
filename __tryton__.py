#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account',
    'name_de_DE': 'Buchhaltung',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': '''Financial and Accounting Module with:
    - General accounting
    - Fiscal year management
    - Taxes management
    - Journal entries
    - Reconciliation

And with reports:
    - General ledger
    - Trial balance
    - Balance sheet
    - Income statement
    - Third party balance
    - Aged balance
    - General journal
''',
    'description_de_DE': '''Buchhaltungsmodul mit:
    - Allgemeiner Buchhaltung
    - Verwaltung von Geschäftsjahren
    - Verwaltung von Steuern
    - Buchführung
    - Abstimmung

Zugehörige Berichte:
    - Hauptbuch
    - Summen- und Saldenliste
    - Bilanzbogen
    - Gewinn- und Verlustrechnung
    - Offene Posten
    - Fälligkeitsliste
    - Allgemeinem Journal
''',
    'depends': [
        'ir',
        'res',
        'company',
        'party',
        'currency',
    ],
    'xml': [
        'account.xml',
        'fiscalyear.xml',
        'period.xml',
        'journal.xml',
        'move.xml',
        'tax.xml',
        'party.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ],
}
