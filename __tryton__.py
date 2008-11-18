#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Google Maps',
    'name_de_DE': 'Google Maps',
    'name_es_ES': 'Google Maps',
    'name': 'Cartes Google',
    'version' : '1.0.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add link from addresses to Google Maps',
    'description_de_DE': 'Fügt einen Link für den automatischen Aufruf von Google Maps zu Adressen hinzu.',
    'description_fr_FR': 'Ajoute un lien sur les adresses vers les cartes de Google',
    'description_es_ES': 'Añade un enlace a la dirección en Google Maps',
    'depends' : [
        'ir',
        'party'
    ],
    'xml' : [
        'address.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
