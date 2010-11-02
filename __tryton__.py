#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Statement',
    'name_de_DE': 'Buchhaltung Bankauszüge',
    'name_es_CO': 'Estado de Cuentas',
    'name_es_ES': 'Estado de cuentas',
    'name_fr_FR': 'Relevé comptable',
    'version': '1.8.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Financial and Accounting Module with:
    - Statement
    - Statement journal
''',
    'description_de_DE': '''Modul für Buchhaltung und Bankauszüge mit
    - Abstimmung von Bankauszügen und Rechnungen
''',
    'description_es_CO': '''Módulo Financiero y Contable con:
    - Estado de cuentas
    - Diario de estado de cuentas
''',
    'description_es_ES': '''Módulo financiero y contable con:
    - Estado de cuentas
    - Diario de estado de cuentas
''',
    'description_fr_FR': '''Module financier et comptable avec:
    - Relevé
    - Journal de relevés
    ''',
    'depends': [
        'account',
        'company',
        'currency',
        'party',
        'account_invoice',
        ],
    'xml': [
        'statement.xml',
        'journal.xml',
        'invoice.xml',
        ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
