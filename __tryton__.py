#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Purchase',
    'name_de_DE': 'Einkauf',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Purchase',
    'description': '''Define purchase order.
Add to product supplier and purchase informations.
Define the purchase price as the supplier price or the cost price.
Add a list of suppliers.

With the possibilities:
    - to follow invoice and packing states from the purchase order.
    - to define invoice method:
        - Manual
        - Based On Order
        - Based On Packing
''',
    'description_de_DE': ''' - Dient der Erstellung von Einkaufsvorgängen (Entwurf, Angebot, Auftrag).
 - Fügt den Artikeln Lieferanten und Einkaufsinformationen hinzu.
 - Erlaubt die Definition des Einkaufspreises als Lieferpreis oder Einkaufspreis.
 - Fügt eine Lieferantenliste hinzu.

Ermöglicht:
    - die Verfolgung des Status von Rechnungsstellung und Versand für Einkäufe
    - die Festlegung der Methode für die Rechnungsstellung:
        - Manuell
        - Nach Auftrag
        - Nach Lieferung
''',
    'depends': [
        'company',
        'party',
        'stock',
        'account',
        'product',
        'account_invoice',
        'workflow',
        'res',
        'ir',
        'currency',
        'account_product',
    ],
    'xml': [
        'purchase.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
