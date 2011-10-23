#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Invoice',
    'name_bg_BG': 'Аналитична фактура',
    'name_de_DE': 'Kostenstellen Rechnungsstellung',
    'name_es_CO': 'Facturación Analítica',
    'name_es_ES': 'Facturación analítica',
    'name_fr_FR': 'Facturation analytique',
    'version': '2.1.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add analytic account on invoice lines and generate analytic lines on the moves of invoice.
''',
    'description_bg_BG': ''' - Добавя аналитична сметна за редове на фактури и генерира аналитични редове за движения от фактура
''',
    'description_de_DE': ''' - Fügt Kostenstellen zu Rechnungszeilen hinzu
 - Erstellt Positionen für Kostenstellen bei Buchung von Rechnungen
''',
    'description_es_CO': ''' - Adición de contabilidad analítica a las líneas de facturación
 -  Generación de líneas analíticas en la factura.
''',
    'description_es_ES': '''Añade una cuenta analítica en las líneas de '''
    '''factura y genera líneas analíticas en los asientos de la factura.''',
    'description_fr_FR': '''Ajoute la comptabilité analytique sur les lignes '''
    '''de facture et génère les lignes analytiques sur les mouvements de la '''
    '''facture.''',

    'depends': [
        'account_invoice',
        'analytic_account',
    ],
    'xml': [
        'invoice.xml',
    ],
    'translation': [
        'locale/bg_BG.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
