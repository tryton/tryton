#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Timesheet',
    'name_bg_BG': 'График',
    'name_ca_ES': 'Fulls de treball',
    'name_de_DE': 'Zeiterfassung',
    'name_es_AR': 'Partes de trabajo',
    'name_es_CO': 'Hoja de Asistencia',
    'name_es_ES': 'Partes de trabajo',
    'name_fr_FR': 'Feuille de présence',
    'name_nl_NL': 'Tijdregistratie',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Timesheet Module with:
    - Work
    - Timesheet line

And with reports:
    - Hours per work
    - Hours per employee per week
    - Hours per employee per month
''',
    'description_bg_BG': '''Модул за график с:
    - Задачи
    - Редове от график

Прилежащи справки:
    - Часове за задача
    - Часове по служител за седмица
    - Часове по служител за месец
''',
    'description_ca_ES': '''Mòdul de fulls de treball amb:
    - Feines o tasques
    - Línies de fulls de treball

I els informes:
    - Hores per tasca
    - Hores per empleat i setmana
    - Hores per empleat i mes
''',
    'description_de_DE': '''Zeiterfassungsmodul mit:
    - Aufgaben
    - Zeitpositionen

Zugehörige Berichte:
    - Stunden pro Aufgabe
    - Stunden pro Mitarbeiter pro Woche
    - Stunden pro Mitarbeiter pro Monat
''',
    'description_es_AR': '''Módulo de partes de trabajo con:
    - Trabajo
    - Línea de parte parte de trabajo

Y con informes:
    - Horas por trabajo
    - Horas por empleado y semana
    - Horas por empleado y mes
''',
    'description_es_CO': '''Módulo de Hoja de Asistencia con:
    - Trabajo
    - Líneas de tiempo laborado

Y con reportes de:
    - Horas por semana
    - Horas por empleado por semana
    - Horas por empleado por mes
''',
    'description_es_ES': '''Módulo de partes de trabajo con:
    - Trabajos o tareas
    - Líneas de parte de trabajo

Y con informes:
    - Horas por trabajo
    - Horas por empleado y semana
    - Horas por empleado y mes
''',
    'description_fr_FR': '''Module feuille de présence, avec:
    - Tâche
    - Ligne de feuille de présence

Et les rapports:
    - Heures par tâche
    - Heures par employé par semaine
    - Heures par employé par mois
''',
    'description_nl_NL': '''Tijdverantwoordingmodule met:
    - Werken
    - Tijdboekingen

Bijbehorende rapporten:
    - Uren per werk
    - Uren per werknemer per week
    - Uren per werknemer per maand
''',
    'depends': [
        'ir',
        'res',
        'company',
        'company_work_time',
    ],
    'xml': [
        'timesheet.xml',
        'work.xml',
        'line.xml',
    ],
    'translation': [
        'locale/cs_CZ.po',
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/de_DE.po',
        'locale/es_AR.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
