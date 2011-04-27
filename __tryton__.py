# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Party - Siret',
    'name_bg_BG' : 'Партньор - SIRET',
    'name_de_DE' : 'Parteien - SIRET',
    'name_es_CO' : 'Terceros - SIRET',
    'name_es_ES': 'Terceros - SIRET',
    'name_fr_FR': 'Tiers - Siret',
    'version' : '2.0.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''
Add SIRET/SIREN number fields on party.
    These numbers are used in France, for geographical identification of
    enterprises:
    - SIREN (Systeme d'Identification du Repertoire des ENtreprises)
    - SIRET (Systeme d'Identification du Repertoire des ETablissements)
''',
    'description_bg_BG' : '''
Добавя SIRET/SIREN полета към партньор.
    SIRET/SIREN са френски еквивалент на БУЛСТАТ и служат географско
    идентифициране на фирма:
    - SIREN (Système d’Identification du Répertoire des ENtreprises)
    - SIRET (Système d’Identification du Répertoire des ETablissements)
''',
    'description_de_DE' : '''
Fügt ein Feld für die SIRET/SIREN-Nummer bei Parteien hinzu.
    Diese Nummern dienen in Frankreich der Identifikation und geographischen
    Zuordnung von Unternehmen:
    - SIREN (Système d’Identification du Répertoire des ENtreprises)
    - SIRET (Système d’Identification du Répertoire des ETablissements)
''',
    'description_es_CO' : '''
Añade campos para los números SIRET/SIREN en Terceros.
    Estos números son utilizados en Francia, para la identificación de
    empresas (SIREN) así como su ubicación geográfica (SIRET).
    - SIREN (Système d’Identification du Répertoire des ENtreprises)
    - SIRET (Système d’Identification du Répertoire des ETablissements)
''',
    'description_es_ES' : '''
Añade campos para los números SIRET/SIREN en Terceros.
    Estos números son utilizados en Francia, para la identificación de
    empresas (SIREN) así como su ubicación geográfica (SIRET).
    - SIREN (Système d’Identification du Répertoire des ENtreprises)
    - SIRET (Système d’Identification du Répertoire des ETablissements)
''',
    'description_fr_FR': '''
Ajoute les champs numéro SIRET/SIREN sur les tiers.
    Ces numéros sont utilisés en France, pour l'identification géographique des
    entreprises :
    - SIREN (Système d’Identification du Répertoire des ENtreprises)
    - SIRET (Système d’Identification du Répertoire des ETablissements)
''',
    'depends' : [
        'ir',
        'party',
    ],
    'xml' : [
        'party.xml',
        'address.xml',
    ],
    'translation': [
        'bg_BG.csv',
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
