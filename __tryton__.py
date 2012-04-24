#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Stock Continental',
    'name_ca_ES': 'Gestió d''estocs continental',
    'name_de_DE': 'Buchhaltung Lagerbewertung Kontinentale Methode',
    'name_es_AR': 'Contabilidad de existencias continental',
    'name_es_ES': 'Gestión de stock continental',
    'name_fr_FR': 'Gestion de stock continentale',
    'version': '2.4.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add continental stock accounting for real-time stock valuation.
''',
    'description_ca_ES': '''Afegeix comptabilitat d'estocs continental per
la valoració d'estocs en temps real.
''',
    'description_de_DE': '''
    - Fügt die kontinentale Methode der Lagerbewertung in Echt-Zeit hinzu.
''',
    'description_es_AR': '''Añade contabilidad de existencias continental para
la valuación de existencias en tiempo real.
''',
    'description_es_ES': '''Añade contabilidad de stocks continental para
la valoración de existencias en tiempo real.
''',
    'description_fr_FR': '''
    Ajoute la gestion de stock continentale pour l'évaluation en temps réel de la valeur du stock
''',
    'depends': [
        'ir',
        'res',
        'account',
        'account_product',
        'stock',
    ],
    'xml': [
        'product.xml',
        'account.xml',
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
