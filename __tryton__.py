#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Cost FIFO',
    'name_bg_BG': 'FIFO цена на продукт',
    'name_ca_ES': 'Cost FIFO de productes',
    'name_de_DE': 'Artikel Kostenpreisermittlung FIFO',
    'name_es_AR': 'Costo FIFO de producto',
    'name_es_CO': 'Costo FIFO de producto',
    'name_es_ES': 'Coste FIFO de producto',
    'name_fr_FR': 'Prix de revient produit FIFO',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add FIFO cost method on the product form.
Once installed, the price of the stock moves from a supplier or to a
customer will update automatically the cost price of the related
product (if the cost price method is FIFO)
''',
    'description_bg_BG': '''Добавя FIFO начин на остойностяване в формата на продукт
    - Добавя FIFO (първи влязъл първи излязъл) като начин на изчисляване на
      цената на продукт.
    - След инсталиране на този модул цената на даден продукт (ако е избран този
      начин на остойностяване) се изчислява автоматично при всяко движение на
      наличност от доставчик или към клиент
''',
    'description_ca_ES': '''Afegeix el mètode de cost FIFO al formulari de producte.
Un cop instal·lat, el preu dels moviments d'estoc des d'un proveïdor o un client,
actualitzarà automàticament el preu de cost del producte relacionat (si el mètode
de càlcul del preu de cost és FIFO).
''',
    'description_de_DE': '''Kostenpreisermittlung für Artikel nach Methode 'FIFO'
    - Fügt 'FIFO' (First In - First Out) zu den Methoden für die
      Kostenpreisermittlung für Artikel hinzu.
    - Nach Installation dieses Moduls wird der Kostenpreis eines Artikels (für
      den die Methode FIFO gewählt wurde) automatisch bei jeder Lagerbewegung
      von einem Lieferanten oder zu einem Kunden angepasst.
''',
    'description_es_AR': '''Añade el método de coste FIFO en el formulario de producto.
Una vez instalado, el precio de los movimientos de stock desde un proveedor o
a un cliente actualizará automáticamente el precio de costo del producto
relacionado (si el método de cálculo del precio de costo es FIFO)
''',
    'description_es_CO': '''Añade el método de costo FIFO al formulario de producto.
Cuando está instalado, el precio de los movimientos de stock desde un proveedor
o a un cliente actualizarán automáticamente el precio de costo del producto
relacionado (Si método del costo de producto es FIFO)
''',
    'description_es_ES': '''Añade el método de coste FIFO en el formulario de producto.
Una vez instalado, el precio de los movimientos de stock desde un proveedor o
a un cliente actualizará automáticamente el precio de coste del producto
relacionado (si el método de cálculo del precio de coste es FIFO)
''',
    'description_fr_FR': '''Ajoute 'FIFO' parmi les méthodes de coût du produit.
Une fois le module installé, le prix de chaque mouvement de stock
depuis un fournisseur ou vers un client modifiera automatiquement le
prix de revient du produit concerné (si la méthode de coût est FIFO).
''',
    'depends': [
        'ir',
        'product',
        'stock',
    ],
    'xml': [
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
