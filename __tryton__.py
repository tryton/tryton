#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Sale',
    'name_de_DE': 'Kostenstellen Verkauf',
    'name_fr_FR': 'Vente analytique',
    'name_es_ES': 'Ventas Analíticas',
    'version': '1.1.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add analytic account on sale lines.
''',
    'description_de_DE': '''Fügt Kostenstellen zu den Verkaufspositionen hinzu
''',
    'description_fr_FR': 'Ajoute la comptabilité analytique sur les lignes de facture',
    'description_es_ES': '''Añade cuentas analíticas a las líneas de ventas.
''',
    'depends': [
        'sale',
        'analytic_account',
        'analytic_invoice',
    ],
    'xml': [
        'sale.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
