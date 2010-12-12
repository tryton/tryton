#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Country',
    'name_de_DE': 'Länder',
    'name_bg_BG': 'Държави',
    'name_es_CO': 'País',
    'name_es_ES': 'País',
    'name_fr_FR': 'Pays',
    'version' : '1.9.0',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Define all countries and subdivisions.',
    'description_bg_BG': 'Задаване на държави и административни единици.',
    'description_de_DE': 'Stellt sämtliche Länder und ihre subnationalen Einheiten zur Verfügung.',
    'description_es_CO': 'Define todos los países y sus subdivisiones.',
    'description_es_ES': 'Define todos los países y sus subdivisiones.',
    'description_fr_FR': 'Défini tous les pays ainsi que leurs subdivisions.',
    'depends' : ['ir', 'res'],
    'xml' : [
        'country.xml',
    ],
    'translation': [
        'bg_BG.csv',
        'cs_CZ.csv',
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
        'ru_RU.csv',
   ],
}
