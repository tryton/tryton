#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'LDAP Authentication',
    'name_bg_BG': 'LDAP Проверка',
    'name_ca_ES': 'Autenticació LDAP',
    'name_de_DE': 'LDAP Authentifizierung',
    'name_es_AR': 'Autentificación LDAP',
    'name_es_CO': 'Autentificación LDAP',
    'name_es_ES': 'Autentificación LDAP',
    'name_fr_FR': 'Authentification LDAP',
    'version': '2.4.0',
    'author': 'B2CK, Josh Dukes & Udo Spallek',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Authenticate users with LDAP server.''',
    'description_bg_BG': 'Проверка на потребители чрез LDAP сървър.',
    'description_ca_ES': '''Autentica els usuaris contra un servidor LDAP.''',
    'description_de_DE': '''Authentifizierung über LDAP
    - Fügt Unterstützung für Authentifizierung über einen LDAP-Server hinzu.
''',
    'description_es_AR': 'Autentifica usuarios contra un servidor LDAP.',
    'description_es_CO': 'Autentica usuarios frente a un servidor LDAP.',
    'description_es_ES': 'Autentifica usuarios contra un servidor LDAP.',
    'description_fr_FR': '''Authentification des utilisateurs via un serveur LDAP.''',
    'depends': [
        'ir',
        'res',
        'ldap_connection',
    ],
    'xml': [
        'connection.xml',
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
