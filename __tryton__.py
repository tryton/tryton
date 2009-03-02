#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Currency',
    'name_de_DE': 'Währung',
    'name_fr_FR': 'Devise',
    'name_es_ES': 'Moneda',
    'version': '1.0.3',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define currencies and exchange rate.
Allow to customize the formatting of the currency amount.
''',
    'description_de_DE': ''' - Ermöglicht die Eingabe von Währungen und Wechselkursen.
 - Erlaubt die beliebige Formatierung von Währungsbeträgen.
''',
    'description_fr_FR': '''Défini les devises et leurs taux de change.
Permet de formater les montants en fonction de la devise.
''',
    'description_es_ES': '''Define las monedas y la tasa de cambio.
Permite personalizar el formato de visualización de la moneda.
''',
    'depends': [
        'ir',
        'res',
    ],
    'xml': [
        'currency.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ]
}
