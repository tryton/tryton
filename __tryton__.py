#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Purchase',
    'name_bg_BG': 'Аналитични покупки',
    'name_ca_ES': 'Compra analítica',
    'name_de_DE': 'Kostenstellen Einkauf',
    'name_es_AR': 'Compra Analítica',
    'name_es_CO': 'Compra Analítica',
    'name_es_ES': 'Compra analítica',
    'name_fr_FR': 'Achat analytique',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add analytic account on purchase lines.
''',
    'description_bg_BG': '''Добавя аналитична сметка към редовете на покупка
''',
    'description_ca_ES': '''Afegeix comptabilitat analítica a les línies de les
comandes de compra.''',
    'description_de_DE': '''Fügt kostenstellen zu Einkaufspositionen hinzu
''',
    'description_es_AR': '''Añade contabilidad analítica a las líneas de compra.
''',
    'description_es_CO': '''Adiciona contabilidad analítica a las líneas de compra.
''',
    'description_es_ES': '''Añade contabilidad analítica a las líneas de los
pedidos de compra.''',
    'description_fr_FR': 'Ajoute la comptabilité analytique sur les lignes d\'achat.',
    'depends': [
        'purchase',
        'analytic_account',
        'analytic_invoice',
    ],
    'xml': [
        'purchase.xml',
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
