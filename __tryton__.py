#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Management',
    'name_de_DE': 'Lagerverwaltung',
    'name_es_CO': 'Inventarios',
    'name_es_ES': 'Gestión de existencias',
    'name_fr_FR': 'Gestion des stocks',
    'version': '1.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Stock Management and Inventory Control with:
    - Location definition
    - Stock move
    - Supplier, Customer and Internal Shipments. Customer and Supplier Return Shipments.
    - Stock Inventory

And with reports:
    - Delivery Note
    - Picking List
    - Restocking List (on Supplier Shipment and Customer Return Shipment)
    - Products by Locations
''',
    'description_de_DE': '''Lagerverwaltung und Bestandskontrolle mit:
    - Definition von Lagerorten
    - Lagerbewegungen
    - Lieferposten Lieferant/Kunde/Intern, Warenrückgaben und Warenrücknahmen
    - Lagerbestandsaktualisierung

Mit den Berichten:
    - Lieferschein
    - Pick Liste
    - Einlagerungsliste (für Lieferposten von Lieferanten und Warenrücknahmen)
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
    'description_es_ES': '''Gestión de Existencias y control de inventarios con:
    - Definición de ubicaciones
    - Movimiento de existencias
    - Envios de proveedores, clientes e internos. Envio de devoluciones de clientes y proveedores.
    - Inventario de existencias

Y con los informes:
    - Notas de envio
    - Lista de selección
    - Lista de recálculo de existencias (con envios de proveedores y envios de devoluciones de clientes)
    - Productos por ubicación
''',
    'description_fr_FR':'''Gestion des stocks et contrôle de l'inventaire avec:
    - Emplacement
    - Mouvement de stock
    - Expédition client, fournisseur et interne. Retour d'expédition client et founisseur.
    - Inventaire

Et les rapports:
    - Bon de livraison client
    - Liste de prélèvement
    - Liste de restockage (sur l'expédition fournisseur et le retour d'expédition client)
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
        'shipment.xml',
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
