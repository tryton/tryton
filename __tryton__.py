# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Measurements',
    'name_de_DE': 'Artikel Abmessungen',
    'name_fr_FR': 'Mesure des produits',
    'name_es_AR': 'Mediciones de Productos',
    'version': '2.3.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add measurements to product',
    'description_de_DE': '''
    - Fügt Abmessungen für Artikel hinzu.
    ''',
    'description_fr_FR': 'Gestion des dimensions de produit',
    'description_es_AR': 'Añade mediciones al producto',
    'depends': [
        'ir',
        'res',
        'product',
    ],
    'xml': [
        'product.xml',
    ],
    'translation': [
        'locale/de_DE.po',
        'locale/fr_FR.po',
        'locale/es_AR.po',
    ]
}
