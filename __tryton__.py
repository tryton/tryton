#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project Plan',
    'name_bg_BG': 'Планиране на проекти',
    'name_de_DE': 'Projekte Planung',
    'name_es_CO': 'Planeación de Proyectos',
    'name_es_ES': 'Planificación de proyecto',
    'name_fr_FR': 'Planification de projet',
    'version': '2.2.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add planning capabilities on projects.
''',
    'description_bg_BG': '''Добавя възможност за планиране на проекти
''',
    'description_de_DE': '''Projektmodul Planung:
    - Fügt Planungsmöglichkeiten für Projekte hinzu
''',
    'description_es_CO': '''Añadir posibilidad de planeación de proyectos.
''',
    'description_es_ES': 'Añade la capacidad de planificación de proyectos.',
    'description_fr_FR': '''Ajoute des fonctionnalités de planification à la gestion de projet.
''',
    'depends': [
        'ir',
        'company',
        'project',
        'timesheet',
    ],
    'xml': [
        'work.xml',
        'allocation.xml',
    ],
    'translation': [
        'locale/cs_CZ.po',
        'locale/bg_BG.po',
        'locale/de_DE.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
