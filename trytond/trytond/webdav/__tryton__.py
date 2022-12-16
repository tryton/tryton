#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'WebDAV',
    'name_bg_BG': 'WebDAV',
    'name_de_DE': 'WebDAV',
    'name_es_ES': 'WebDAV',
    'name_fr_FR': 'WebDAV',
    'name_nl_NL': 'WebDAV',
    'name_ru_RU': 'WebDAV',
    'description': '''Basic module providing concept and administration of integrated WebDAV features.
''',
    'description_bg_BG': '''Общ модул предоставящ представа и администрация на интегрирани WebDAV услуги.
''',
    'description_de_DE': '''Basismodul für Konzept und Administration der integrierten WebDAV-Komponente
''',
    'description_es_ES': '''Módulo basico que provee el concepto y la administración de servicios WebDAV integrados.
''',
    'description_fr_FR': '''Module de base fournissant les concepts et l'administration des fonctionnalités integrées de WebDAV.
''',
    'description_nl_NL': '''Basismodule voor het instellen en beheren van de geïntegreerde WebDAV functionaliteit
''',
    'description_ru_RU': '''Базовый модуль обеспечения и управления встроенными функциями WebDAV.
''',
    'active': True,
    'depends': [
        'ir',
        'res',
    ],
    'xml': [
        'webdav.xml',
    ],
    'translation': [
        'locale/cs_CZ.po',
        'locale/bg_BG.po',
        'locale/fr_FR.po',
        'locale/de_DE.po',
        'locale/es_ES.po',
        'locale/es_CO.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
