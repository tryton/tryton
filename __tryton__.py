#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Product',
    'name_de_DE': 'Buchhaltung Artikel',
    'name_fr_FR': 'Compte produit',
    'name_es_CO': 'Contabilidad de Inventarios',
    'name_es_ES': 'Contabilidad de Inventarios',
    'version': '1.2.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add accounting properties on product and category like:
    - account for expense / revenue
    - taxes for customer / supplier
''',
    'description_de_DE': '''Fügt Eigenschaften für die Buchhaltung zu Artikeln und Artikelkategorien hinzu:
    - Aufwands- und Ertragskonto
    - Steuern für Kunden und Lieferanten
''',
    'description_fr_FR': '''Ajoute des propriétés comptables sur les produits et leurs caétgories:
    - comptes de dépense et revenu
    - taxes client et fournisseur
''',
    'description_es_CO': '''Adiciona propiedades contables en productos y categorías:
    - contabilidad para gastos / ganancias
    - impuestos para cliente / proveedor
''',
    'description_es_ES': '''Adiciona propiedades contables en productos y categorías:
    - contabilidad para gastos / ganancias
    - impuestos para cliente / proveedor
''',
    'depends': [
        'ir',
        'account',
        'company',
        'product',
    ],
    'xml': [
        'product.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ]
}
