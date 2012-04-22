# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Carrier Percentage',
    'name_de_DE': 'Frachtkosten Prozentsatz',
    'name_fr_FR': 'Coût transporteur: pourcentage',
    'name_es_AR': 'Transportistas: Porcentaje',
    'version': '2.3.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add cost method based on percentage',
    'description_de_DE': '''
    - Fügt eine Kostenmethode basierend auf Prozentsatz hinzu.
    ''',
    'description_fr_FR': 'Ajoute une méthode de coût basée sur le pourcentage.',
    'description_es_AR': 'Añade método de costo basado en porcentaje',
    'depends': [
        'ir',
        'res',
        'carrier',
        'currency',
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
        'locale/es_AR.po',
        ],
    }
