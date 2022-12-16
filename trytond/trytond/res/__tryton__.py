#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Res',
    'name_bg_BG': 'Ресурс',
    'name_ca_ES': 'Recursos interns',
    'name_de_DE': 'Benutzerverwaltung',
    'name_es_AR': 'Gestión de usuarios',
    'name_es_ES': 'Recursos internos',
    'name_fr_FR': 'Ressource',
    'name_nl_NL': 'Interne handelingen',
    'name_ru_RU': 'Базовые ресурсы сервера',
    'description': '''Basic module handling internal tasks of the application.
Provides concepts and administration of users and internal communication.
''',
    'description_bg_BG': '''Основен модул управляващ вътрешните задачи на приложението

 - Предоставя идеи и администрация на потребители и вътрешна комуникация
''',
    'description_ca_ES': '''Mòdul bàsic que gestiona tasques internes de l'aplicació.
Proporciona els conceptes i administració d'usuaris i comunicació interna.
''',
    'description_de_DE': '''Basismodul für interne Aufgaben der Anwendung

 - Stellt Konzept und Administration für die Benutzerverwaltung und interne Kommunikation zur Verfügung
''',
    'description_es_AR': '''Módulo básico que gestiona tareas internas de la aplicación.

 - Provee los conceptos y administración de usuarios y comunicación interna.
''',
    'description_es_ES': '''Módulo básico que gestiona tareas internas de la aplicación.
Proporciona los conceptos y administración de usuarios y comunicación interna.
''',
    'description_fr_FR': '''Module de base gérant les tâches internes de l'application.
Fournit les concepts et l'administration des utilisateurs et de la communication interne.
''',
    'description_nl_NL': '''Basis module voor de afhandeling van interne taken.
    Regelt instellingen en beheer van gebruikers en interne communicatie.
''',
    'description_ru_RU': '''Базовый модуль обработки внутренних задач приложения.
    Обеспечивает концепции и администрирование пользователей и внутренней связи.
''',
    'active': True,
    'depends': ['ir'],
    'xml': [
        'res.xml',
        'group.xml',
        'user.xml',
        'request.xml',
        'ir.xml',
        ],
    'translation': [
        'locale/cs_CZ.po',
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/fr_FR.po',
        'locale/de_DE.po',
        'locale/es_AR.po',
        'locale/es_ES.po',
        'locale/es_CO.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
