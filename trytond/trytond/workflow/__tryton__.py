#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Workflow',
    'name_de_DE': 'Workflow',
    'description': '''Basic module providing concept and administration of workflows.
''',
    'description_de_DE': '''Basismodul für Konzept und Administration von Workflows
''',
    'active': True,
    'depends': ['ir', 'res'],
    'xml': [
        'workflow.xml',
        ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
        'es_CO.csv',
    ],
}
