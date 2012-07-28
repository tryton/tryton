#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Split',
    'name_de_DE': 'Lager Aufteilung Lagerbewegung',
    'name_es_ES': 'Partición stock',
    'name_fr_FR': 'Division des mouvements de stock',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Allow to split move.',
    'description_de_DE': '''Ermöglicht die Aufteilung einer Lagerbewegung.''',
    'description_es_ES': '''Permite partir un movimiento de stock.''',
    'description_fr_FR': '''Division des mouvements de stock.''',
    'depends': [
        'ir',
        'stock',
    ],
    'xml': [
        'stock.xml',
    ],
    'translation': [
        'locale/de_DE.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
    ],
}
