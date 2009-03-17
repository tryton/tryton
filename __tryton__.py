#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name" : "Stock Supply with Week Days",
    "name_fr_FR" : "Approvisionnement par jours de semaine",
    "version" : "0.0.1",
    "author" : "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": '''Define the delivery days of the week by suppliers.
Impact supply dates computations.
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
        'fr_FR.csv',
    ],
}
