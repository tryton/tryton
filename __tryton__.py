# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Country',
    'name_de_DE': 'Länder',
    'name_bg_BG': 'Държави',
    'name_es_CO': 'País',
    'name_es_ES': 'País',
    'name_fr_FR': 'Pays',
    'name_ru_RU': 'Страны',
    'version' : '2.2.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Define all countries and subdivisions.',
    'description_bg_BG': 'Задаване на държави и административни единици.',
    'description_de_DE': 'Stellt sämtliche Länder und ihre subnationalen Einheiten zur Verfügung.',
    'description_es_CO': 'Define todos los países y sus subdivisiones.',
    'description_es_ES': 'Define todos los países y sus subdivisiones.',
    'description_fr_FR': 'Défini tous les pays ainsi que leurs subdivisions.',
    'description_ru_RU': 'Определение всех стран и административных единиц',
    'depends' : ['ir', 'res'],
    'xml' : [
        'country.xml',
    ],
    'translation': [
        'locale/bg_BG.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
   ],
}
