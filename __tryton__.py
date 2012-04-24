#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Inventory for many locations',
    'name_bg_BG': 'Инвентаризация на наличност за много местонахождения',
    'name_ca_ES': 'Inventari de moltes ubicacions',
    'name_de_DE': 'Lagerverwaltung Bestandskorrektur für mehrere Lagerorte',
    'name_es_AR': 'Inventario de existencias para muchas ubicaciones',
    'name_es_CO': 'Inventario de existencias para muchas ubicaciones',
    'name_es_ES': 'Inventario de stock para muchas ubicaciones',
    'name_fr_FR': 'Inventaire de stock par liste de locations',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add a wizard that allows to create automatically inventories for a
given list of locations.
''',
    'description_bg_BG': '''Добавя помощник, който позволява създаване на автоматични
      инвентаризации за зададен списък от местонахождения
''',
    'description_ca_ES': '''Afegeix un assistent per permetre crear inventaris
automàtics per a una llista d'ubicacions donada.''',
    'description_de_DE': '''Bestandskorrektur für mehrere Lagerorte
    - Fügt einen Wizard hinzu, der automatisch die Lagerbestände für eine Liste
      von Lagerorten erzeugt.
''',
    'description_es_AR': '''Añade un asistente que permite crear inventarios
automáticos para una lista dada de ubicaciones.
''',
    'description_es_CO': '''Añade un asistente que permite crear inventarios
automáticos para una lista dada de ubicaciones.
''',
    'description_es_ES': '''Añade un asistente que permite crear inventarios
automáticos para una lista dada de ubicaciones.
''',
    'description_fr_FR': '''Ajoute un wizard qui permet de créer automatiquement des inventaires
pour une liste donnée d'emplacements.
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
