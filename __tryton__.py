#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Invoice',
    'name_de_DE': 'Kostenstellen Rechnungsstellung',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add analytic account on invoice lines and generate analytic lines on the moves of invoice.
''',
    'description_de_DE': ''' - Fügt Kostenstellen zu Rechnungszeilen hinzu
 - Erstellt Positionen für Kostenstellen bei Buchung von Rechnungen
''',
    'depends': [
        'account_invoice',
        'analytic_account',
    ],
    'xml': [
        'invoice.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
