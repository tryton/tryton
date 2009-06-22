#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Belgium',
    'version': '1.2.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': '''Define an account chart template for Belgium.
Usefull to create a Belgium account chart with the wizard in
"Financial Management>Configuration>General Account>Create Chart of Account from Template".
''',
    'depends': [
        'account',
    ],
    'xml': [
        'account_be.xml',
        'tax_be.xml',
    ],
}
