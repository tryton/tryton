#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Cost History',
    'name_fr_FR': 'Historique prix de revient produit',
    'version': '1.1.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Historize the product cost.
This module add a button on the product form which open the list of
all the past value of the cost price of the current product.
''',
    'description_fr_FR': '''Historique du prix de revient du produit.
Ce module ajoute un bouton sur la fiche produit qui ouvre la liste de
toutes les valeurs passées du prix de revient du produit.

''',
    'depends': [
        'ir',
        'product',
    ],
    'xml': [
        'product.xml',
    ],
    'translation': [
        'fr_FR.csv',
    ],
}
