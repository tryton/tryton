#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Price List',
    'name_bg_BG': 'Ценова листа на продукт',
    'name_ca_ES': 'Tarifes de producte',
    'name_de_DE': 'Artikel Preisliste',
    'name_es_AR': 'Lista de precios de producto',
    'name_es_CO': 'Lista de precios de producto',
    'name_es_ES': 'Tarifas de producto',
    'name_fr_FR': 'Liste de prix produit',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define price list rules by parties.''',
    'description_bg_BG': 'Задаване на правила на ценова листа по партньор.',
    'description_ca_ES': '''Defineix regles de tarifa per tercer.''',
    'description_de_DE': '''Preislisten für Artikel
    - Ermöglicht die Definition von Preislisten für Parteien.
''',
    'description_es_AR': 'Define reglas de lista de precios por tercero.',
    'description_es_CO': 'Define reglas de lista de precios por tercero.',
    'description_es_ES': 'Define reglas de tarifa por tercero.',
    'description_fr_FR': '''Défini des listes de prix par tiers''',
    'depends': [
        'ir',
        'product',
        'party',
        'company',
    ],
    'xml': [
        'price_list.xml',
        'party.xml',
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
