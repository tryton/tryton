#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Invoice History',
    'name_bg_BG': 'Хронология на фактуриране',
    'name_de_DE': 'Fakturierung Historisierung',
    'name_es_CO': 'Histórico de Facturación',
    'name_es_ES': 'Histórico de facturación',
    'name_fr_FR': 'Historisation facture',
    'version': '2.0.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add historization for Invoice fields.
''',
    'description_bg_BG': '''Добавя хронология към полетата на фактура
''',
    'description_de_DE': '''Fügt Historisierung zu den Rechnungsfeldern hinzu
''',
    'description_es_CO': '''Histórico de Facturación a nivel de campos
''',
    'description_es_ES': 'Añade un histórico para los campos de factura',
    'description_fr_FR': '''Ajoute l'historisation au champs de la facture.
''',
    'depends': [
        'account_invoice',
        'party',
    ],
    'xml': [
    ],
    'translation': [
        'bg_BG.csv',
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ]
}
