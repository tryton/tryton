#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Sale',
    'name_de_DE': 'Verkauf',
    'name_es_CO': 'Ventas',
    'name_es_ES': 'Ventas',
    'name_fr_FR': 'Vente',
    'version': '1.2.5',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Sale',
    'description': '''Define sale order.
Add to product sale informations.
Define the sale price as the list price.

With the possibilities:
    - to follow invoice and packing states from the sale order.
    - to define invoice method:
        - Manual
        - On Order Confirmed
        - On packing Sent
    - to define packing method:
        - Manual
        - On Order Confirmed
        - On Invoice Paid
''',
    'description_de_DE': ''' - Dient der Erstellung von Verkaufsvorgängen (Entwurf, Angebot, Auftrag).
 - Fügt den Artikeln Einkaufsinformationen hinzu.
 - Erlaubt die Definition des Einkaufspreises als Listenpreis.

Ermöglicht:
    - die Verfolgung des Status von Rechnungsstellung und Versand für Verkäufe
    - die Festlegung der Methode für die Rechnungsstellung:
        - Manuell
        - Nach Auftragsbestätigung
        - Nach Versand
    - die Festlegung der Methode für den Versand:
        - Manuell
        - Nach Auftragsbestätigung
        - Nach Bezahlung
''',
    'description_es_CO': ''' - Define la orden de Ventas.
 - Se añade al producto la información de ventas.
 - Definición del precio de venta y el precio de lista.

 - Con las posibilidades de:
    - seguir los estados de facturación y empaque desde la orden de venta.
    - definir el método de facturación:
        - Manual
        - Al Confirmar la Orden
        - Al Envío del Paquete
    - definir el método de empaque:
        - Manual
        - Al Confirmar la Orden
        - Contra el Pago de la Factura
''',
    'description_es_ES': ''' - Define la orden de Ventas.
 - Se añade al producto la información de ventas.
 - Definición del precio de venta y el precio de lista.

 - Con las posibilidades de:
    - seguir los estados de facturación y empaque desde la orden de venta.
    - definir el método de facturación:
        - Manual
        - Al Confirmar la Orden
        - Al Envío del Paquete
    - definir el método de empaque:
        - Manual
        - Al Confirmar la Orden
        - Contra el Pago de la Factura
''',
    'description_fr_FR': '''Défini l'ordre de vente.
Ajoute au produit les information de vente.

Avec la possibilité:
    ' de suivre l'état de la facture et du colisage depuis l'ordre de vente
    ' de choisir entre plusieurs méthodes de facturation:
        ' Manuelle
        ' Sur confirmation de la commande
        ' À la livraison
    ' de choisir entre plusieurs méthodes de colisage:
        ' Manuel
        ' Sur confirmation de la commande
        ' Au paiement de la facture
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
        'sale.xml',
        'party.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
