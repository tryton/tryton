# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Party',
    'name_fr_FR': 'Tiers',
    'name_de_DE': 'Kontakte',
    'version' : '0.0.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category' : 'Generic',
    'description': 'Define parties, addresses and co.',
    'description_fr_FR': 'Définit des tiers, des adresses, etc.',
    'description_de_DE': 'Ermöglicht die Erstellung von Kontakten, Adressen, etc.',
    'depends' : [
        'ir',
        'res',
        'country',
    ],
    'xml' : [
        'party.xml',
        'category.xml',
        'address.xml',
        'contact_mechanism.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ],
}
