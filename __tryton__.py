# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Measurements',
    'name_bg_BG': 'Управление мерки на продукти',
    'name_ca_ES': 'Mesures de productes',
    'name_de_DE': 'Artikel Abmessungen',
    'name_fr_FR': 'Mesure des produits',
    'name_es_AR': 'Mediciones de Productos',
    'name_es_ES': 'Medidas de productos',
    'version': '2.3.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add measurements to product',
    'description_ca_ES': 'Afegeix mesures al producte (longitud, alt, ample, pes).',
    'description_de_DE': '''
    - Fügt Abmessungen für Artikel hinzu.
    ''',
    'description_fr_FR': 'Gestion des dimensions de produit',
    'description_es_AR': 'Añade mediciones al producto',
    'description_es_ES': 'Añade medidas al producto (longitud, alto, ancho, peso).',
    'depends': [
        'ir',
        'res',
        'product',
    ],
    'xml': [
        'product.xml',
    ],
    'translation': [
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/fr_FR.po',
        'locale/es_AR.po',
        'locale/es_ES.po',
        'locale/es_CO.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ]
}
