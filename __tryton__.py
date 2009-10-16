#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'LDAP Authentication',
    'name_de_DE' : 'LDAP Authentifizierung',
    'name_fr_FR': 'Authentification LDAP',
    'version': '1.3.0',
    'author': 'B2CK, Josh Dukes & Udo Spallek',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Authenticate users with LDAP server.''',
    'description_de_DE' : '''Authentifizierung über LDAP
    - Fügt Unterstützung für Authentifizierung über einen LDAP-Server hinzu.
''',
    'description': '''Authentification des utilisateurs via un serveur LDAP.''',
    'depends': [
        'ir',
        'res',
        'ldap_connection',
    ],
    'xml': [
        'connection.xml',
    ],
    'translation': [
        'de_DE.csv',
    ],
}
