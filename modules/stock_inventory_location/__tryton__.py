#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Inventory for many locations',
    'name_fr_FR': 'Inventaire de stock par liste de locations',
    'name_de_DE': 'Lagerverwaltung Bestandskorrektur für mehrere Lagerorte',
    'name_es_ES': 'Inventario de existencias para muchas ubicaciones',
    'name_es_CO': 'Inventario de existencias para muchas ubicaciones',
    'version': '1.2.2',
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
    'description_de_DE': '''Bestandskorrektur für mehrere Lagerorte
    - Fügt einen Wizard hinzu, der automatisch die Lagerbestände für eine Liste
      von Lagerorten erzeugt.
    - Ermöglicht die Filterung der Auswahl nach Artikel oder Artikelkategorie.
''',
    'description_es_ES': '''Añade un asistente que permite crear inventarios
automáticos para una lista de ubicaciones dada. También permite filtrar por
producto y categorías de producto.
    ''',
    'description_es_CO': '''Añade un asistente que permite crear inventarios
automáticos para una lista dada de ubicaciones.  También permite filtrar
por producto y categorías de producto.
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
        'de_DE.csv',
        'es_ES.csv',
        'es_CO.csv',
    ],
}
