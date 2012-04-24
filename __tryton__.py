#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name": "Stock Product Location",
    "name_bg_BG": "Местонахождение на наличност на продукт",
    'name_ca_ES': 'Ubicació d''estoc de producte',
    "name_de_DE": "Lagerverwaltung Artikel Lagerort",
    "name_es_AR": "Ubicación de existencias de producto",
    "name_es_CO": "Ubicación de existencias de producto",
    "name_es_ES": "Ubicación de stock de producto",
    "name_fr_FR": "Emplacement de produit",
    "version": "2.4.0",
    "author": "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": '''Define default storage location by warehouse on product.
Theses locations will be used by the supplier shipment for generating
inventory moves.
''',
    "description_bg_BG": '''Задаване на местонахождение по подрабиране на
    на продукт по склад. Тези местонахождения ще бъдат използвани при пратки
    от доставчик за генериране на движения за инвентаризация.
''',
    'description_ca_ES': '''Defineix la ubicació interna predeterminada per
magatzem i producte. Aquestes ubicacions s'utilitzaran en l'enviament de proveïdor
per generar moviments d'inventari.
''',
    "description_de_DE": '''Standardlagerorte für Artikel
    - Ermöglicht die Definition von Standardlagerorten für Artikel in einem Warenlager
    - Diese Lagerorte werden von Lieferposten von Lieferanten für die
      Lagerbewegungen benutzt
''',
    "description_es_AR": '''Define la ubicación del almacén predeterminado por
depósito y producto.
Estas ubicaciones se utilizarán en el envio de proveedor para generar movimientos
de inventario.
''',
    "description_es_CO": '''Define la ubicación de almacenamiento predeterminada
por depósito y producto.
Esta ubicación la utilizará el envío del proveedor para generar movimientos
de inventaio.
''',
    "description_es_ES": '''Define la ubicación interna predeterminada por almacén y producto.
Estas ubicaciones se utilizarán en el envío de proveedor para generar movimientos de inventario.
''',
    "description_fr_FR": '''Defini un emplacement de rangement par défaut par produit.
Ces emplacements seront utilisés par les colisages fournisseurs pour
générer les mouvements internes.
''',
    "depends": [
        "ir",
        "product",
        "stock",
    ],
    "xml": [
        "location.xml",
        "product.xml",
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
