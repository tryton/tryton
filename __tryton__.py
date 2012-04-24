#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Purchase',
    'name_bg_BG': 'Покупки',
    'name_ca_ES': 'Compres',
    'name_de_DE': 'Einkauf',
    'name_es_AR': 'Compras',
    'name_es_CO': 'Compras',
    'name_es_ES': 'Compras',
    'name_fr_FR': 'Achat',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define purchase order.
Add product supplier and purchase informations.
Define the purchase price as the supplier price or the cost price.

With the possibilities:
    - to follow invoice and shipment states from the purchase order.
    - to define invoice method:
        - Manual
        - Based On Order
        - Based On Shipment
''',
    'description_bg_BG': ''' Задаване на поръчки за покупки.
 - Добавяне на доставчици на продукти и информация за покупки.
 - Задаване на цената на покупка като цена на доствчик или фабричната цена.

Със следните възможности:
    - проследяване на фактури и състоянията на доставката от поръчка за покупка
    - задаване на начини на фактуриране:
        - Ръчно
        - Въз основа на поръчка
        - Въз основа на доставка
''',
    'description_ca_ES': '''- Defineix comandes de compra.
- Afegeix informació de proveïdor i de compra als productes.
- Defineix el preu de compra com el preu de proveïdor o preu de cost.

Amb la possibilitat de:

- Seguir l'estat de facturació i enviament des de la comanda de compra.
- Definir el mètode de facturació:
    - Manual
    - Basat en la comanda de compra
    - Basat en l'albarà de sortida
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
    'description_es_AR': '''Define órdenes de compra.
 - Añade información de proveedor y de compra de un producto.
 - Define el precio de compra como el precio del proveedor o el precio de coste.

 - Con la posibilidad de:
    - seguir el estado de facturación y envio desde la orden de compra.
    - definir el método de facturación:
        - Manual
        - Basado en orden
        - Basado en envio
''',
    'description_es_CO': ''' - Definición de orden de compras.
 - Se añade información de proveedor y de compra de un producto.
 - Se define el precio de compra con el precio de proveedor o costo.

 - Con la posibilidad de:
    - seguir el estado de facturación y empaque desde la orden de compra.
    - elegir el método de facturación:
        - Manual
        - Basado en Orden
        - Basado en Empaque
''',
    'description_es_ES': '''- Define pedidos de compra.
- Añade información de proveedor y de compra a los productos.
- Define el precio de compra como el precio del proveedor o el precio de coste.

Con la posibilidad de:
    - Seguir el estado de facturación y envío desde el pedido de compra.
    - Definir el método de facturación:
        - Manual
        - Basado en el pedido
        - Basado en el envío
''',
    'description_fr_FR': '''Defini l'ordre d'achat.
Ajoute les fournisseurs et les informations d'achat sur le produit.
Défini un prix d'achat par fournisseur et un prix de revient.

Avec la possibilité:
    - de suivre les états de la facture et du colis depuis la commande d'achat.
    - de choisir la méthode de facturation:
        - Manuelle
        - Sur base de la commande
        - Sur base du colis
''',
    'depends': [
        'company',
        'party',
        'stock',
        'account',
        'product',
        'account_invoice',
        'res',
        'ir',
        'currency',
        'account_product',
    ],
    'xml': [
        'purchase.xml',
        'configuration.xml',
        'party.xml',
        'stock.xml',
        'product.xml',
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
