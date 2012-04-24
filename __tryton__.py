#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Sale',
    'name_bg_BG': 'Аналитична продажба',
    'name_ca_ES': 'Venda analítica',
    'name_de_DE': 'Kostenstellen Verkauf',
    'name_es_AR': 'Venta Analítica',
    'name_es_CO': 'Ventas Analíticas',
    'name_es_ES': 'Venta analítica',
    'name_fr_FR': 'Vente analytique',
    'version': '2.4.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add analytic account on sale lines.
''',
    'description_bg_BG': '''Добавя аналитична сметка към редове от продажба
''',
    'description_ca_ES': '''Afegeix comptabilitat analítica a les línies de les
comandes de venda.''',
    'description_de_DE': '''Fügt Kostenstellen zu den Verkaufspositionen hinzu
''',
    'description_es_AR': '''Añade contabilidad analítica a las líneas de venta.
''',
    'description_es_CO': '''Añade cuentas analíticas a las líneas de ventas.
''',
    'description_es_ES': '''Añade contabilidad analítica a las líneas de los
pedidos de venta.''',
    'description_fr_FR': 'Ajoute la comptabilité analytique sur les lignes de facture',
    'depends': [
        'sale',
        'analytic_account',
        'analytic_invoice',
    ],
    'xml': [
        'sale.xml',
    ],
    'translation': [
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_AR.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
