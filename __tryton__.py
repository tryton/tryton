#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project Plan',
    'name_de_DE': 'Projekte Planung',
    'name_es_CO': 'Planeación de Proyectos',
    'name_es_ES': 'Planificación de proyecto',
    'name_fr_FR': 'Planification de projet',
    'version': '1.6.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add planning capabilities on projects.
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
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
