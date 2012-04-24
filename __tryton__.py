# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Product',
    'name_bg_BG': 'Продукт',
    'name_ca_ES': 'Productes',
    'name_de_DE': 'Artikel',
    'name_es_AR': 'Productos',
    'name_es_CO': 'Productos',
    'name_es_ES': 'Productos',
    'name_fr_FR': 'Produit',
    'name_nl_NL': 'Producten',
    'name_ru_RU': 'ТМЦ',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Define products, categories of product, units ' \
        'of measure, categories of units of measure.',
    'description_bg_BG': 'Задаване на продукти, категории продукти, мерни единици, категории мерни единици.',
    'description_ca_ES': '''Defineix productes, categories de producte, unitats
de mesura, categories d'unitats de mesura.''',
    'description_de_DE': 'Dient der Erstellung von Artikeln, Artikelkategorien, Maßeinheiten und Kategorien für Maßeinheiten.',
    'description_es_AR': '''Define:
 - Productos
 - Categorías de producto
 - Unidades de medida
 - Categorías de unidades de medida
''',
    'description_es_CO': 'Definición de productos, categorías de producto unidades de medida y categorías de unidades de medida',
    'description_es_ES': 'Define productos, categorías de producto, unidades de medida y categorías de unidades de medida.',
    'description_fr_FR': '''Défini:
 - Produit
 - Catégorie de produit
 - Unité de mesure
 - Catégorie d'unité de mesure
''',
    'description_nl_NL': 'Definieert producten, productcategorieën, meeteenheden en categorieën van meeteenheden.',
    'description_ru_RU': 'Определение ТМЦ, категорий ТМЦ, единиц измерения, категорий единиц измерения.',
    'depends': [
        'ir',
        'res',
    ],
    'xml': [
        'product.xml',
        'category.xml',
        'uom.xml',
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
    ]
}
