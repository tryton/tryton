#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Cost FIFO',
    'name_fr_FR': 'Prix de revient produit FIFO',
    'name_de_DE': 'Artikel Kostenpreisermittlung FIFO',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add FIFO cost method on the product form.
Once installed, the price of the stock moves from a supplier or to a
customer will update automatically the cost price of the related
product (if the cost price method is FIFO)
''',
    'description_fr_FR':'''Ajoute 'FIFO' parmi les méthodes de coût du produit.
Une fois le module installé, le prix de chaque mouvement de stock
depuis un fournisseur ou vers un client modifiera automatiquement le
prix de revient du produit concerné (si la méthode de coût est FIFO).
''',
    'description_de_DE':'''Kostenpreisermittlung für Artikel nach Methode 'FIFO'
    - Fügt 'FIFO' (First In - First Out) zu den Methoden für die
      Kostenpreisermittlung für Artikel hinzu.
    - Nach Installation dieses Moduls wird der Kostenpreis eines Artikels (für
      den die Methode FIFO gewählt wurde) automatisch bei jeder Lagerbewegung
      von einem Lieferanten oder zu einem Kunden angepasst.
''',
    'depends': [
        'ir',
        'product',
        'stock',
    ],
    'xml': [
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
    ],
}
