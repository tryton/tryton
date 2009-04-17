#This file is part of Tryton. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'German Account Chart SKR03',
    'name_de_DE': 'Deutscher Kontenrahmen SKR03',
    'version': '1.1.0',
    'author': 'virtual things',
    'email': 'info@virtual-things.biz',
    'website': 'http://www.virtual-things.biz/',
    'description': '''Financial and Accounting Module (only for Germany):
    - Provides Account Chart SKR03
    ''',
    'description_de_DE': '''Buchhaltungsmodul (nur für Deutschland):
    - Stellt den Kontenrahmen SKR03 zur Verfügung
''',
    'depends': [
        'account',
    ],
    'xml': [
        'account_de.xml',
    ],
}
