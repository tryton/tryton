#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name": "Purchase Invoice Line Standalone",
    "name_bg_BG": "Ред от независима фактура към покупка",
    'name_ca_ES': 'Línia de factura de compra independent',
    "name_de_DE": "Einkauf ungebundene Rechnungsposition",
    "name_es_AR": "Línea de factura de compra independiente",
    "name_es_CO": "Línea de Factura autónoma en Compras",
    "name_es_ES": "Línea de factura de compra independiente",
    "name_fr_FR": "Ligne de facture autonome - Achat",
    "version": "2.4.0",
    "author": "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": '''
Change the purchase order behaviour to create standalone invoice lines instead of a
complete invoice. This allow to compose invoices with lines originating
from differents purchases.
''',
    "description_bg_BG": '''Покупка с независима фактура
    - Промяна на поведението при поръчка за покупка като вместо пълна фактура
      създава редове с независими фактури.
    - Позволява създаване на фактури с редове от различни покупки.
''',
    'description_ca_ES': '''Modifica el comportament de les comandes de compra
perquè crei línies de factura enlloc d'una factura completa. Això permet crear
factures amb línies provinents de diferents compres.
''',
    "description_de_DE": '''Einkäufe mit ungebundenen Rechnungspositionen
    - Ändert das Verhalten im Einkaufsvorgang, indem unabhängige Rechnungspositionen
      an Stelle einer kompletten Rechnung erstellt werden.
    - Ermöglicht die Zusammenstellung von Rechnungen aus Einkaufspositionen
      verschiedener Einkäufe.
''',
    "description_es_AR": '''
Modifica el comportamiento de la orden de compra permitiendo crear líneas
independientes en lugar de una factura completa. Esto permite componer
facturas con líneas originadas en diferentes compras.
''',
    "description_es_CO": '''Modifica el comportamiento de orden de compra permitiendo crear
líneas autónomas en lugar de una factura completa. Permite componer facturas con
líneas originadas en diferentes compras.
''',
    "description_es_ES": '''Modifica el comportamiento de los pedidos de compra permitiendo crear
líneas de factura independientes en lugar de una factura completa. Esto permite crear
facturas con líneas que procedan de distintas compras.
''',
    "description_fr_FR": '''Modifie le comportement de l'ordre d'achat pour créer des lignes de
facture autonomes au lieu de factures complètes. Cela permet de
composer des factures avec des lignes provenant de différents achats.
''',
    "depends": [
        "ir",
        "purchase",
        "account_invoice_line_standalone",
    ],
    "xml": [
        "purchase.xml",
    ],
    'translation': [
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_AR.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
