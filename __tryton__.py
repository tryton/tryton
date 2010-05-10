# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Party',
    'name_de_DE': 'Parteien',
    'name_es_CO': 'Terceros',
    'name_es_ES': 'Terceros',
    'name_fr_FR': 'Tiers',
    'version' : '1.6.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Define parties, addresses and co.',
    'description_de_DE': 'Ermöglicht die Erstellung von Parteien, Adressen, etc.',
    'description_es_CO': 'Definición de terceros, direcciones, etc.',
    'description_es_ES': 'Define terceros, direcciones, etc...',
    'description_fr_FR': 'Définit des tiers, des adresses, etc.',
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
        'configuration.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
