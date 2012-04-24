# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Carrier Weight',
    'name_bg_BG': 'Управление на превозвачи: Тегло',
    'name_ca_ES': 'Transportistes: Pesatge',
    'name_de_DE': 'Frachtkosten Gewicht',
    'name_fr_FR': 'Coût transporteur: Poid',
    'name_es_AR': 'Transportistas: Pesaje',
    'name_es_ES': 'Transportistas: Pesaje',
    'version': '2.4.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add cost method based on weight',
    'description_ca_ES': 'Afegeix mètode de cost basat en el pes.',
    'description_de_DE': '''
    - Fügt eine Kostenmethode basierend auf Gewicht hinzu.
    ''',
    'description_fr_FR': 'Ajoute une méthode de coût basée sur le poids.',
    'description_es_AR': 'Añade método de costo basado en el peso',
    'description_es_ES': 'Añade método de coste basado en el peso.',
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
        ],
    }
