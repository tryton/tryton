#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account French',
    'name_fr_FR': 'Comptabilité française',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define an account chart template for French.
Usefull to create a French account chart with the wizard in
"Financial Management>Configuration>General Account>Create Chart of Account from Template".
''',
    'description_fr_FR': '''Défini le plan comptable pour la France.
''',
    'depends': [
        'account',
    ],
    'xml': [
        'account_fr.xml',
        'tax_fr.xml',
    ],
}
