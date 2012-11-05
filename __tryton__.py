#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Production Management',
    'name_ca_ES': 'Producció',
    'name_de_DE': 'Produktion',
    'name_es_ES': 'Producción',
    'name_fr_FR': 'Production',
    'version': '2.4.2',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Production Management with:
    - Bill of Material
    - Production Order
    ''',
    'description_ca_ES': '''Gestió de la producció amb:
    - Llistes de Material (LdM)
    - Ordres de producció
    ''',
    'description_es_ES': '''Gestión de la producción con:
    - Listas de Material (LdM)
    - Órdenes de producción
    ''',
    'description_de_DE': '''Verwaltung der Produktion mit
    - Stücklisten
    - Produktionsaufträgen
    ''',
    'description_fr_FR': '''Gestion de la production, avec:
    - Nomenclature
    - Ordre de production
    ''',
    'depends': [
        'ir',
        'res',
        'product',
        'company',
        'stock',
    ],
    'xml': [
        'production.xml',
        'configuration.xml',
        'bom.xml',
        'product.xml',
        'stock.xml',
    ],
    'translation': [
        'locale/de_DE.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
    ]
}
