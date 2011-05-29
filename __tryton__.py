#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Management',
    'name_de_DE': 'Lagerverwaltung',
    'name_es_CO': 'Inventarios',
    'name_es_ES': 'Inventarios',
    'name_fr_FR': 'Gestion des stocks',
    'version': '1.2.8',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Stock Management and Inventory Control with:
    - Location definition
    - Stock move
    - Shipment: Supplier, Customer or Internal
    - Stock Inventory

And with reports:
    - Customer Shipment
    - Products by Locations
''',
    'description_de_DE': '''Lagerverwaltung und Bestandskontrolle mit:
    - Definition von Lagerorten
    - Lagerbewegungen
    - Packlisten/Lieferscheine Lieferant / Kunde / Intern
    - Lagerbestand

Zugehörige Berichte:
    - Lieferschein für Kunden
    - Artikel nach Lagerorten
''',
    'description_es_CO': '''Administración de Inventarios y bodegas:
    - Definición de sitios
    - Movimiento de Bodega
    - Empaque de Proveedor / Cliente / Interno
    - Inventario en Bodega

Y con los reportes:
    - Empaques de Clientes
    - Productos por Lugar
''',
    'description_es_ES': '''Administración de Inventarios y bodegas:
    - Definición de sitios
    - Movimiento de Bodega
    - Empaque de Proveedor / Cliente / Interno
    - Inventario en Bodega

Y con los reportes:
    - Empaques de Clientes
    - Productos por Lugar
''',
    'description_fr_FR':'''Gestion des stocks et contrôle de l'inventaire avec:
    - Emplacement
    - Mouvement de stock
    - Colisages client / fournisseur / interne
    - Inventaire

Et les rapports:
    - Colisage client
    - Quantités de produit par location
''',
    'depends': [
        'ir',
        'workflow',
        'party',
        'product',
        'company',
        'currency',
    ],
    'xml': [
        'stock.xml',
        'product.xml',
        'location.xml',
        'packing.xml',
        'move.xml',
        'inventory.xml',
        'party.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
