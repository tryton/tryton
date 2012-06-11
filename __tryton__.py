#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Supply Production',
    'name_ca_ES': 'Proveïment d''estoc en producció',
    'name_es_ES': 'Abastecimiento de stock en producción',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Supply Stock with Production''',
    'description_ca_ES': '''Proveïment d'estoc en producció.''',
    'description_es_ES': '''Abastecimiento de stock en producción.''',
    'depends': [
        'ir',
        'product',
        'stock',
        'production',
        'stock_supply',
        ],
    'xml': [
        'production.xml',
        ],
    'translation': [
        ]
}
