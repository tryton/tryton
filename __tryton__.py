# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Party - Siret',
    'name_de_DE' : 'Parteien - SIRET',
    'name_fr_FR': 'Tiers - Siret',
    'version' : '0.0.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add SIRET/SIREN number on party',
    'description_de_DE' : '''
Fügt ein Feld für die SIRET/SIREN-Nummer bei Parteien hinzu.
    Diese Nummern dienen in Frankreich der Identifikation und geographischen
    Zuordnung von Unternehmen:
    - SIREN (Système d’Identification du Répertoire des ENtreprises)
    - SIRET (Système d’Identification du Répertoire des ETablissements)
''',
    'description_fr_FR': 'Ajoute le numéro SIRET/SIREN sur les tiers',
    'depends' : [
        'ir',
        'party',
    ],
    'xml' : [
        'party.xml',
        'address.xml',
    ],
    'translation': [
        'de_DE.csv',
        'fr_FR.csv',
    ],
}
