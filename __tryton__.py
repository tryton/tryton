#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name" : "Stock Supply with Week Day",
    "version" : "0.0.1",
    "author" : "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "category" : "Inventory",
    "description": "Define the delivery day of the week by suppliers.",
    "depends" : [
        "ir",
        "purchase",
    ],
    "xml" : [
        "purchase.xml",
    ],
    'translation': [
    ],
}
