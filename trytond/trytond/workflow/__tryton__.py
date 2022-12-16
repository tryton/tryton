#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Workflow',
    'name_bg_BG': 'Работен процес',
    'name_de_DE': 'Workflow',
    'name_es_ES': 'Flujo de trabajo',
    'name_fr_FR': 'Workflow',
    'name_nl_NL': 'Werkgang',
    'name_ru_RU': 'Бизнес процессы',
    'description': '''Basic module providing concept and administration of workflows.
''',
    'description_bg_BG': '''Основен модул даващ идея и администрация на работни процеси.
''',
    'description_de_DE': '''Basismodul für Konzept und Administration von Workflows
''',
    'description_es_ES': '''Módulo básico que provee el concepto y administración de flujos de trabajo.
''',
    'description_fr_FR': '''Module de base fournissant les concepts et l'administration de workflows.
''',
    'description_nl_NL': '''Basismodule voor het instellen en beheren van werkgangen.
''',
    'description_ru_RU': '''Базовый модуль концепция обеспечения и администрирования рабочих процессов.
''',
    'active': True,
    'depends': ['ir', 'res'],
    'xml': [
        'workflow.xml',
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
