#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'IR',
    'name_bg_BG': 'Вътрешна администрация',
    'name_de_DE': 'Interne Administration',
    'name_es_ES': 'Administración interna',
    'name_fr_FR': 'Administration Interne',
    'name_nl_NL': 'Interne administratie',
    'name_ru_RU': 'Внутреннее управление',
    'description': '''Basic module handling internal tasks of the application.
Provides concepts and administration of models, actions, sequences, localizations, cron jobs etc.
''',
    'description_bg_BG': '''Общ модул за вътрешните задачи на приложението

 - Предлага предсатва и адмнинистрация на модули, десйтвия, последователности, преводи, планировщици и тн.
''',
    'description_de_DE': '''Basismodul für interne Aufgaben der Anwendung

 - Stellt Konzept und Administration für Modelle, Aktionen, Sequenzen, Lokalisierungen, Zeitplaner etc. zur Verfügung
''',
    'description_es_ES': '''Módulo básico que gestiona las tareas internas de la aplicación.
 - Provee los conceptos y administración de modelos, acciones, secuencias, localización, tareas programadas, etc...
''',
    'description_fr_FR': '''Module de base gérant les tâches internes de l'application.
Fournit les concepts et l'administration des modèles, actions, séquences, localizations, planificateur de tâches etc.
''',
    'description_nl_NL': '''Basismodule voor interne taken binnen het programma.

 - Instellen en beheren van modellen, acties, reeksen, lokalisaties, herhalende taken enz.
''',
    'description_ru_RU': '''Базовый модуль обработки внутренних задач приложения.
    Обеспечивает концепций и моделей, администрация, действия, последовательность, локализация, Cron Jobs т.д.
''',
    'active': True,
    'xml': [
        'ir.xml',
        'ui/ui.xml',
        'ui/icon.xml',
        'ui/menu.xml',
        'ui/view.xml',
        'action.xml',
        'model.xml',
        'sequence.xml',
        'attachment.xml',
        'cron.xml',
        'lang.xml',
        'translation.xml',
        'export.xml',
        'rule.xml',
        'property.xml',
        'module/module.xml',
        'trigger.xml',
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
