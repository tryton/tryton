# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product Cost History',
    'name_bg_BG': 'История за цена на продукт',
    'name_de_DE': 'Artikel Kostenpreis Historisierung',
    'name_es_AR': 'Histórico del precio de costo de producto',
    'name_es_CO': 'Histórico del costo para productos',
    'name_es_ES': 'Histórico del precio de coste de producto',
    'name_fr_FR': 'Historique prix de revient produit',
    'name_ru_RU': 'История цен ТМЦ',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Historize the product cost.
This module add a button on the product form which open the list of
all the past value of the cost price of the current product.
''',
    'description_bg_BG': '''История на цена на продукт.
    - Този модул добавя бутон към формата за продукт който отваря списък
      с себестойността във времето на текущия продукт.
''',
    'description_de_DE': '''Historisierung für Kostenpreise von Artikeln
    - Fügt einen Knopf auf dem Artikelformular hinzu, der eine Liste mit sämtlichen
      Werten aus der Vergangenheit für den Kostenpreis des Artikels öffnet.
''',
    'description_es_AR': '''Genera un histórico del precio de costo de producto.
Este módulo añade un botón en el formulario de producto que abre la lista de
todos los valores pasados del precio de costo del producto actual.
''',
    'description_es_CO': '''Genera el histórico de costo para el producto.
Este módulo añade un botón en el formulario de producto que abre la lista
de todos los costos anteriores para el producto actual.
''',
    'description_es_ES': '''Genera un histórico del precio de coste de producto.
Este módulo añade un botón en el formulario de producto que abre la lista de
todos los valores pasados del precio de coste del producto actual.
''',
    'description_fr_FR': '''Historique du prix de revient du produit.
Ce module ajoute un bouton sur la fiche produit qui ouvre la liste de
toutes les valeurs passées du prix de revient du produit.
''',
    'description_ru_RU': '''История цен ТМЦ.
Этот модуль добавляет кнопку для ТМЦ c помощью которой открывается список
всех предыдущих значений цен на текущий ТМЦ.
''',
    'depends': [
        'ir',
        'product',
    ],
    'xml': [
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
