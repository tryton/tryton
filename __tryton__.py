#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Invoice History',
    'name_de_DE': 'Fakturierung Historisierung',
    'name_es_ES': 'Histórico de Facturación',
    'version': '1.1.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add historization for Invoice fields.
''',
    'description_de_DE': '''Fügt Historisierung zu den Rechnungsfeldern hinzu
''',
    'description_es_ES': '''Histórico de Facturación a nivel de campos
''',
    'depends': [
        'account_invoice',
        'party',
    ],
    'xml': [
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ]
}
