#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Management',
    'name_de_DE': 'Lagerverwaltung',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Inventory',
    'description': '''Stock Management and Inventory Control with:
    - Location definition
    - Stock move
    - Packing Supplier / Customer / Internal
    - Stock Inventory

And with reports:
    - Customer Packing
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
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
