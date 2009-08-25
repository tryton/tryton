#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name" : "Purchase Invoice Line Standalone",
    "name_de_DE" : "Einkauf ungebundene Rechnungsposition",
    "name_fr_FR" : "Ligne de facture autonome - Achat",
    "version" : "0.0.1",
    "author" : "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": '''
Change the purchase order behaviour to create standalone invoice lines instead of a
complete invoice. This allow to compose invoices with lines originating
from differents purchases.
''',
    "description_de_DE": '''Einkäufe mit ungebundenen Rechnungspositionen
    - Ändert das Verhalten im Einkaufsvorgang, indem unabhängige Rechnungspositionen
      an Stelle einer kompletten Rechnung erstellt werden.
    - Ermöglicht die Zusammenstellung von Rechnungen aus Einkaufspositionen
      verschiedener Rechnungen.
''',
    "description_fr_FR": '''Modifie le comportement de l'ordre d'achat pour créer des lignes de
facture autonomes au lieu de factures complètes. Cela permet de
composer des factures avec des lignes provenant de différents achats.
''',
    "depends" : [
        "ir",
        "purchase",
        "account_invoice_line_standalone",
    ],
    "xml" : [
        "purchase.xml",
    ],
    'translation': [
        'de_DE.csv',
        'fr_FR.csv',
    ],
}
