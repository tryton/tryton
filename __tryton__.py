#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Product',
    'name_de_DE': 'Artikel',
    'name_fr_FR': 'Produit',
    'name_es_ES': 'Productos',
    'version' : '1.0.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Define products, categories of product, units ' \
        'of measure, categories of units of measure.',
    'description_de_DE': 'Dient der Erstellung von Artikeln, Artikelkategorien, Maßeinheiten und Kategorien für Maßeinheiten.',
    'description_es_ES': 'Definición de productos, categorías de producto '
    'unidades de medida y categorías de unidades de medida',
    'depends' : [
        'ir',
        'res',
    ],
    'xml' : [
        'product.xml',
        'category.xml',
        'uom.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ]
}

