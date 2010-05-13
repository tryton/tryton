#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project',
    'name_de_DE': 'Projekte',
    'name_es_CO': 'Proyectos',
    'name_es_ES': 'Proyecto',
    'name_fr_FR': 'Projet',
    'version': '1.6.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Project Module with:
    - Project management
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
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
