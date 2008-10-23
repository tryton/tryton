#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name" : "Google Maps",
    "version" : "0.0.1",
    "author" : "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "category" : "Generic",
    "description": "Add link from addresses to Google Maps",
    "depends" : [
        "ir",
        "party"
    ],
    "xml" : [
        "address.xml",
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
