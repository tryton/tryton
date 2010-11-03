#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Product',
    'name_de_DE': 'Artikel',
    'name_es_CO': 'Productos',
    'name_es_ES': 'Producto',
    'name_fr_FR': 'Produit',
    'version': '1.6.2',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Define products, categories of product, units ' \
        'of measure, categories of units of measure.',
    'description_de_DE': 'Dient der Erstellung von Artikeln, Artikelkategorien, Maßeinheiten und Kategorien für Maßeinheiten.',
    'description_es_CO': 'Definición de productos, categorías de producto unidades de medida y categorías de unidades de medida',
    'description_es_ES': 'Define productos, categorías de producto, unidades de medida y categorías de unidades de medida',
    'description_fr_FR': '''Défini:
 - Produit
 - Catégorie de produit
 - Unité de mesure
 - Catégorie d'unité de mesure
''',
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
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ]
}

