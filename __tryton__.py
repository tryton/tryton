#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name" : "Stock Supply with Week Days",
    "name_de_DE" : "Lagerverwaltung Bestellwesen nach Wochentagen",
    "name_es_CO" : "Existencias por días de la semana",
    "name_es_ES" : "Suministro de existencias por días de la semana",
    "name_fr_FR" : "Approvisionnement par jours de semaine",
    "version" : "1.8.1",
    "author" : "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": '''Define the delivery days of the week by suppliers.
Impact supply dates computations.
''',
    "description_de_DE": '''Bestellwesen nach Wochentagen
    - Ermöglicht die Definition von Liefertagen pro Lieferant.
    - Wirkt sich auf die Berechnung von Lieferzeitpunkten aus.
 ''',
    "description_es_CO": '''Define los días de la semana para proveedores.
Afecta los cálculos de fecha de los suministros.
''',
    "description_es_ES": '''Define los días de la semana de entrega por proveedores.
Afecta al cálculo de las fechas de suministro.
''',
    "description_fr_FR": '''Défini les jours de livraisons par fournisseurs.
Impacte les calculs de dates de livraisons.
 ''',
    "depends" : [
        "ir",
        "purchase",
    ],
    "xml" : [
        "purchase.xml",
    ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
