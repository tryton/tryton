#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'LDAP Authentification',
    'version': '1.3.0',
    'author': 'B2CK, Josh Dukes & Udo Spallek',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Authenticate users with LDAP server.''',
    'depends': [
        'ir',
        'res',
        'ldap_connection',
    ],
    'xml': [
        'connection.xml',
    ],
    'translation': [
    ],
}
