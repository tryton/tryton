#This file is part of Tryton. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'German Chart of Accounts SKR03',
    'name_ca_ES': 'Pla comptable alemany SKR03',
    'name_de_DE': 'Deutscher Kontenrahmen SKR03',
    'name_es_AR': 'Plan de cuentas alemán SKR03',
    'name_es_ES': 'Plan contable alemán SKR03',
    'name_fr_FR': 'Plan comptable allemand SKR03',
    'version': '2.4.0',
    'author': 'virtual things',
    'email': 'info@virtual-things.biz',
    'website': 'http://www.virtual-things.biz/',
    'description': '''Financial and accounting module (only for Germany):
    - Provides chart of accounts SKR03
    - Provides account structure like balance and income statement
    - Provides taxes, tax groups, tax rules
    - Provides tax codes for german tax report (UStVA)
    ''',
    'description_ca_ES': '''Mòdul financer i comptable (només per Alemanya):
    - Proporciona el pla comptable SKR03
    - Proporciona l'estructura comptable de balanços i pèrdues i guanys
    - Proporciona impostos, grups d'impostos i regles d'impostos
    - Proporciona els codis d'impostos per l'informe d'impostos alemany (UStVA)
''',
    'description_de_DE': '''Buchhaltungsmodul (für Deutschland):
    Stellt den Kontenrahmen SKR03 zur Verfügung mit
    - Bilanzgegliederten Konten
    - Steuern, Steuergruppen und Steuerregeln
    - Steuerkennziffern für die UStVA
''',
    'description_es_ES': '''Módulo financiero y contable (sólo para Alemania):
    - Proporciona el plan contable SKR03
    - Proporciona la estructura contable de balances y pérdidas y ganancias
    - Proporciona impuestos, grupos de impuestos y reglas de impuestos
    - Proporciona los códigos de impuestos para el informe de impuestos alemán (UStVA)
''',
    'description_fr_FR': '''Défini le plan comptable allemand SKR03.
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
