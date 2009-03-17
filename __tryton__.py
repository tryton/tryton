#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name" : "Account Invoice Line Standalone",
    "version" : "1.1.0",
    "author" : "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": "Allow to create standalone invoice line and add it later to an invoice.",
    "depends" : [
        "ir",
        "account_invoice",
    ],
    "xml" : [
        "invoice.xml",
    ],
    'translation': [
        'fr_FR.csv',
    ],
}
