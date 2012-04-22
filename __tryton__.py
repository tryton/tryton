#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Management',
    'name_bg_BG': 'Управление на наличности',
    'name_ca_ES': 'Estocs',
    'name_de_DE': 'Lagerverwaltung',
    'name_es_AR': 'Gestión de existencias',
    'name_es_CO': 'Inventarios',
    'name_es_ES': 'Gestión de existencias',
    'name_fr_FR': 'Gestion des stocks',
    'name_ru_RU': 'Управление складами',
    'version': '2.3.0',
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
    'description_bg_BG': '''Управление на наличности и контрол на инвентаризация с:
    - Задаване на местонахождения
    - Движения на наличност
    - Пратки за клиент, от доставчик, вътрешни пратки. Върнати пратки от клиент и за доставчик.
    - Инвентаризация на наличност

Със следните справки:
    - Бележка за доставка
    - Опаковъчен лист
    - Преизчисляване на инвентарен опис (при пратка на доставчик и пратка върната от клиент)
    - Продукти по местонахождение
''',
    'description_ca_ES': '''Gestió d'estocs i control d'inventaris amb:
- Definició d'ubicacions
- Moviments d'estoc
- Albarans de proveïdors, clients i interns. Albarans de devolució a client i proveïdor.

Amb informes:
- Nota d'entrega
- Albarà intern o de picking
- Llista de realcul d'estocs (en recepcions de proveïdors i de devolucions de clients)
- Productes per ubiació
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
    'description_es_AR': '''Gestión de Existencias y control de inventarios con:
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
    'description_fr_FR': '''Gestion des stocks et contrôle de l'inventaire avec:
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
    'description_ru_RU': '''Управление складами и запасами:
    - Определение мест хранения
    - Складские перемещения
    - Приход, отгрузки, внутренние перемещения. Возвраты поставщикам и от заказчиков.
    - Складской учет

И с отчетами:
    - Доставка
    - Упаковка
    - Инвентаризация (на приход от поставщиков и возвраты клиентов)
    - ТМЦ по местам хранения
''',
    'depends': [
        'ir',
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
        'configuration.xml',
        'period.xml',
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
    ],
}
