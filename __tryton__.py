#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Purchase',
    'name_bg_BG': 'Аналитични покупки',
    'name_de_DE': 'Kostenstellen Einkauf',
    'name_es_CO': 'Compra Analítica',
    'name_es_ES': 'Compra analítica',
    'name_fr_FR': 'Achat analytique',
    'version': '2.0.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add analytic account on purchase lines.
''',
    'description_bg_BG': '''Добавя аналитична сметка към редовете на покупка
''',
    'description_de_DE': '''Fügt kostenstellen zu Einkaufspositionen hinzu
''',
    'description_es_CO': '''Adiciona contabilidad analítica a las líneas de compra.
''',
    'description_es_ES': 'Añade contabilidad analítica a las líneas de compra.',
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
        'bg_BG.csv',
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
