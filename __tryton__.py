# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Carrier',
    'name_de_DE': 'Frachtführer',
    'version' : '0.0.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Define carriers.',
    'description_de_DE': '''
    - Ermöglicht die Definition von Frachtführern.
    ''',
    'depends' : [
        'ir',
        'res',
        'party',
        'product',
    ],
    'xml' : [
        'carrier.xml',
    ],
    'translation': [
        'de_DE.csv',
    ],
}
