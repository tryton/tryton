# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Purchase Shipment Cost',
    'version': '2.3.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add purchase shipment cost',
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
    ],
}
