#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
{
    "name" : "Product",
    "version" : "0.1",
    "author" : "B2CK",
    'website': 'http://www.tryton.org/',
    "category" : "Generic",
    "description": "Define products, categories of product, units" \
        "of measure, categories of units of measure.",
    "depends" : [
        "ir",
        "res",
    ],
    "xml" : [
        "product.xml",
        "category.xml",
        "uom.xml",
    ],
    'translation': [
        'fr_FR.csv',
    ]
}

