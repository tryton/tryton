# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Purchase Shipment Cost',
    'name_bg_BG': 'Управление остойностяване на доставка на покупка',
    'name_de_DE': 'Einkauf Versandkosten',
    'name_fr_FR': 'Coût des expéditions fournisseur',
    'name_es_AR': 'Compras: Costo de envíos',
    'name_es_ES': 'Coste de envío en las compras',
    'version': '2.4.3',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add purchase shipment cost',
    'description_de_DE': '''
    - Fügt Versandkosten für Einkäufe hinzu.
    ''',
    'description_fr_FR': 'Ajoute la gestion des coûts des expéditions '\
        'fournisseur.',
    'description_es_AR': 'Añade costo de envío a la compra',
    'description_es_ES': 'Añade coste de envío en las compras',
     'depends': [
        'ir',
        'res',
        'carrier',
        'currency',
        'stock',
    ],
    'extras_depend': [
        'account_stock_continental',
        'account_product',
        ],
    'xml': [
        'stock.xml',
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
