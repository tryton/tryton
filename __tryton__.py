# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Carrier Weight',
    'name_de_DE': 'Frachtkosten Gewicht',
    'name_fr_FR': 'Coût transporteur: Poid',
    'version': '2.3.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add cost method based on weight',
    'description_de_DE': '''
    - Fügt eine Kostenmethode basierend auf Gewicht hinzu.
    ''',
    'description_fr_FR': 'Ajoute une méthode de coût basée sur le poids.',
    'depends': [
        'ir',
        'res',
        'product',
        'product_measurements',
        'carrier',
        'currency',
        'company',
        ],
    'extras_depend': [
        'purchase_shipment_cost',
        'sale_shipment_cost',
        ],
    'xml': [
        'carrier.xml',
        ],
    'translation': [
        'locale/de_DE.po',
        'locale/fr_FR.po',
        ],
    }
