#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Supply Management',
    'name_bg_BG': 'Управление на доставка на наличност',
    'name_ca_ES': 'Gestió del proveïment d''estocs',
    'name_de_DE': 'Lagerverwaltung Bestellwesen',
    'name_es_AR': 'Gestión de suministro de existencias',
    'name_es_CO': 'Gestión de pedidos de inventario',
    'name_es_ES': 'Gestión del abastecimiento de stock',
    'name_fr_FR': 'Gestion des approvisionnements de stock',
    'version': '2.4.0',
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
    'description_bg_BG': '''Модул за управление на доставка на наличност с:
    - Пренареждане
    - Заявка за покупка

С планировщици:
    - за генериране на заявки за покупка въз основа на пренареждания
    - за генериране на вътрешни пратки въз основа на пренареждания
''',
    'description_ca_ES': '''Mòdul per la gestió del proveïment d'estocs amb:
    - Estocs mínims
    - Peticions de compra

I planificadors:
    - Per generar peticions de compra basades en estocs mínims
    - Per generar albarans interns basats en estocs mínims
''',
    'description_de_DE': '''Modul für das Bestellwesen mit:
    - Bestellpunkten
    - Auftragserstellung

Mit automatischer Auftragserstellung per Zeitplaner:
    - für Bestellungen auf der Basis von Bestellpunkten
    - für interne Lieferposten auf der Basis von Bestellpunkten
''',
    'description_es_AR': '''Módulo de gestión de suministros con:
    - Punto de orden
    - Solicitud de compra

Con tareas programadas para:
    - generar solicitudes de compra basados en puntos de orden
    - generar envios internos basados en puntos de orden
''',
    'description_es_CO': '''Módulo de Administración de pedidos:
    - Punto de Orden
    - Solicitud de Compras

Con agendadores para:
    - generar solicitudes de compra basados en puntos de orden
    - generar empaques internos basados en puntos de orden
''',
    'description_es_ES': '''Módulo para la gestión de abastecimientos con:
    - Reglas de stock mínimo
    - Solicitudes de compra

Con planificadores para:
    - Generar solicitudes de compra basadas en stocks mínimos
    - Generar envíos internos basados en stocks mínimos
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
        'locale/cs_CZ.po',
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/de_DE.po',
        'locale/es_AR.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ]
}
