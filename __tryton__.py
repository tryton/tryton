#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name" : "Stock Product Location",
    "name_fr_FR" : "Emplacement de produit",
    "name_de_DE" : "Lagerverwaltung Artikel Lagerort",
    "version" : "0.0.1",
    "author" : "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": '''Define default storage location by warehouse on product.
Theses locations will be used by the supplier shipment for generating
inventory moves.
''',
    "description_fr_FR": '''Defini un emplacement Magasin par défaut par produit.
Ces emplacements seront utilisés par les colisages fournisseurs pour
générer les mouvements internes.
''',
    "description_de_DE": '''Standardlagerorte für Artikel
    - Ermöglicht die Definition von Standardlagerorten für Artikel in einem Warenlager
    - Diese Lagerorte werden von Lieferposten von Lieferanten für die
      Lagerbewegungen benutzt
''',
    "depends" : [
        "ir",
        "product",
        "stock",
    ],
    "xml" : [
        "location.xml",
        "product.xml",
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
    ],
}
