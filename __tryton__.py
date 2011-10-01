#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Supply Management',
    'name_de_DE': 'Lagerverwaltung Bestellwesen',
    'name_es_CO': 'Gestión de pedidos de inventario',
    'name_es_ES': 'Gestión de suministro de existencias',
    'name_fr_FR': 'Gestion des approvisionnements de stock',
    'version': '1.8.3',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Supply Management Module with:
    - Order point
    - Purchase Request

With schedulers:
    - to generate purchase requests based on order points
    - to generate internal shipments based on order points
''',
    'description_de_DE': '''Modul für das Bestellwesen mit:
    - Bestellpunkten
    - Auftragserstellung

Mit automatischer Auftragserstellung per Zeitplaner:
    - für Bestellungen auf der Basis von Bestellpunkten
    - für interne Lieferposten auf der Basis von Bestellpunkten
''',
    'description_es_CO': '''Módulo de Administración de pedidos:
    - Punto de Orden
    - Solicitud de Compras

Con agendadores para:
    - generar solicitudes de compra basados en puntos de orden
    - generar empaques internos basados en puntos de orden
''',
    'description_es_ES': '''Módulo de gestión de suministros con:
    - Punto de orden
    - Solicitud de compra

Con tareas programadas para:
    - generar solicitudes de compra basados en puntos de orden
    - generar envios internos basados en puntos de orden
''',
    'description_fr_FR': '''Module de gestion des approvisionnements avec:
    - Règles d'approvisionnement
    - Demandes d'achat

Et les planificateurs pour générer:
    - des demandes d'achat et
    - des colisages internes
sur base des règles d'approvisionnement
''',
    'depends': [
        'ir',
        'res',
        'product',
        'stock',
        'purchase',
        'party',
        'account',
    ],
    'xml': [
        'order_point.xml',
        'purchase_request.xml',
        'shipment.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ]
}
