#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Google Maps',
    'name_bg_BG': 'Google карти',
    'name_ca_ES': 'Mapes de Google',
    'name_de_DE': 'Google Maps',
    'name_es_AR': 'Mapas de Google',
    'name_es_CO': 'Mapas de Google',
    'name_es_ES': 'Mapas de Google',
    'name_fr_FR': 'Cartes Google',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add link from addresses to Google Maps',
    'description_bg_BG': 'Добавя връзка към адрес от Google карти.',
    'description_ca_ES': '''Afegeix un enllaç a les adreces per obrir-les amb
el Google Maps.
''',
    'description_de_DE': 'Fügt einen Link für den automatischen Aufruf von Google Maps zu Adressen hinzu.',
    'description_es_AR': 'Añade un enlace de la dirección a Google Maps',
    'description_es_CO': 'Añade un enlace a la dirección en Google Maps',
    'description_es_ES': 'Añade un enlace en las direcciones para abrirlas con Google Maps.',
    'description_fr_FR': 'Ajoute un lien sur les adresses vers les cartes de Google',
    'depends': [
        'ir',
        'party'
    ],
    'xml': [
        'address.xml',
    ],
    'translation': [
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_AR.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
