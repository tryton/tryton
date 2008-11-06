#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name" : "Stock Product Location",
    "version" : "0.0.1",
    "author" : "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": "Define default storage location by warehouse on product.",
    "depends" : [
        "ir",
        "product",
        "stock",
    ],
    "xml" : [
        "location.xml",
        "product.xml",
    ],
    'translation': [
    ],
}
