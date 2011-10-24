# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Carrier',
    'name_es_ES' : 'Transportista',
    'name_de_DE': 'Frachtführer',
    'name_fr_FR': 'Transporteur',
    'version' : '2.2.0',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Define carriers.',
    'description_es_ES': 'Define transportistas.',
    'description_de_DE': '''
    - Ermöglicht die Definition von Frachtführern.
    ''',
    'description_fr_FR': 'Définit des transporteurs.',
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
        'locale/bg_BG.po',
        'locale/cs_CZ.po',
        'locale/es_ES.po',
        'locale/es_CO.po',
        'locale/de_DE.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
