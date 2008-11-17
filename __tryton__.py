#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Analytic Invoice',
    'name_de_DE': 'Kostenstellen Rechnungsstellung',
    'name_fr_FR': 'Facturation analytique',
    'name_es_ES': 'Facturación Analítica',
    'version': '1.1.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add analytic account on invoice lines and generate analytic lines on the moves of invoice.
''',
    'description_de_DE': ''' - Fügt Kostenstellen zu Rechnungszeilen hinzu
 - Erstellt Positionen für Kostenstellen bei Buchung von Rechnungen
''',
    'description_es_ES': ''' - Adición de contabilidad analítica a las líneas de facturación 
 -  Generación de líneas analíticas en la factura.
''',
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
        'de_DE.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
