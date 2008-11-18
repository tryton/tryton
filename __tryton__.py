#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Country',
    'name_de_DE': 'Länder',
    'name_fr_FR': 'Pays',
    'name_es_ES': 'País',
    'version' : '1.0.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Define all countries and subdivisions.',
    'description_de_DE': 'Stellt sämtliche Länder und ihre subnationalen Einheiten zur Verfügung.',
    'description_fr_FR': 'Défini tous les pays ainsi que leurs subdivisions.',
    'description_es_ES': 'Define todos los países y sus subdivisiones.',
    'depends' : ['ir', 'res'],
    'xml' : [
        'country.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
   ],
}
