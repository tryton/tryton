#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Forecast',
    'name_fr_FR': 'Prévision de stock',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',

    'description': '''Provide the "Forecast" model in Inventory Management.
The Forecast form allow to define the expected stock movement towards
customers in any period of time in the future. A wizard allow to
compute the expected quantities with respect to a period in the
past. Once the form confirmed, the corresponding moves are created and
spread homogeneously across the period. Those moves will allow other
process to take forecasts into account.
''',

    'description_fr_FR':'''Fournit le modèle "Prévision" dans la gestion des stocks.
Le formulaire de prévision permet de définir les mouvements attendus
vers les clients pour n'importe quelle période dans le futur. Un
wizard permet de calculer les quantités attendues en fonction d'une
période dans le passé. A la validation du formulaire, les mouvements
correspondants sont créés et répartis sur la période donnée. Ces
mouvement permettent aux autres processus de prendre en compte les
prévisions.
''',

    'depends': [
        'ir',
        'res',
        'workflow',
        'stock',
        'product',
        'company',
    ],
    'xml': [
        'forecast.xml',
    ],
    'translation': [
        'fr_FR.csv',
    ],
}
