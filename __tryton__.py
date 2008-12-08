#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name" : "Purchase Invoice Line Standalone",
    "version" : "0.0.1",
    "author" : "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": "Change the purchase to create standalone invoice line.",
    "depends" : [
        "ir",
        "purchase",
        "account_invoice_line_standalone",
    ],
    "xml" : [
        "purchase.xml",
    ],
    'translation': [
    ],
}
