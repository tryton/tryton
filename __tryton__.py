#This file is part of Tryton. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'German Chart of Accounts SKR03',
    'name_de_DE': 'Deutscher Kontenrahmen SKR03',
    'version': '2.2.0',
    'author': 'virtual things',
    'email': 'info@virtual-things.biz',
    'website': 'http://www.virtual-things.biz/',
    'description': '''Financial and accounting module (only for Germany):
    - Provides chart of accounts SKR03
    - Provides account structure like balance and income statement
    - Provides taxes, tax groups, tax rules
    - Provides tax codes for german tax report (UStVA)
    ''',
    'description_de_DE': '''Buchhaltungsmodul (für Deutschland):
    Stellt den Kontenrahmen SKR03 zur Verfügung mit
    - Bilanzgegliederten Konten
    - Steuern, Steuergruppen und Steuerregeln
    - Steuerkennziffern für die UStVA
''',
    'depends': [
        'account',
    ],
    'xml': [
        'account_de.xml',
    ],
    'translation': [
        'locale/de_DE.po',
    ],
}
