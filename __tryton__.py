#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project',
    'name_bg_BG': 'Проект',
    'name_de_DE': 'Projekte',
    'name_es_CO': 'Proyectos',
    'name_es_ES': 'Proyecto',
    'name_fr_FR': 'Projet',
    'version': '2.2.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Project Module with:
    - Project management
''',
    'description_bg_BG': '''Модул за проекти с:
    - Управление на проекти
''',
    'description_de_DE': '''Projektmodul für:
    - Projektverwaltung
''',
    'description_es_CO': '''Módulo de proyectos con:
    - Gestión de proyectos
''',
    'description_es_ES': '''Módulo de proyecto con:
    - Gestión de proyecto
''',
    'description_fr_FR': '''Module projet avec:
    - Gestion de projet
''',
    'depends': [
        'ir',
        'timesheet',
        'party',
        'company_work_time',
    ],
    'xml': [
        'project.xml',
        'work.xml',
    ],
    'translation': [
        'locale/bg_BG.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
