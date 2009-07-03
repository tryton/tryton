#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Inventory for many locations',
    'name_fr_FR': 'Inventaire de stock par liste de locations',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add a wizard that allows to create automatically inventories for a
given list of locations. It also allows to filter by product and
categories of product.
    ''',
    'description_fr_FR': '''Ajoute un wizard qui permet de créer automatiquement des inventaires
pour une liste donnée d'emplacements. Il permet aussi de filtrer par
produit et par catégorie de produit.
''',
    'depends': [
        'ir',
        'stock',
        'company',
        'product',
    ],
    'xml': [
        'inventory.xml',
    ],
    'translation': [
        'fr_FR.csv',
    ],
}
