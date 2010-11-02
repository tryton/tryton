#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Timesheet',
    'name_de_DE': 'Zeiterfassung',
    'name_es_CO': 'Hoja de Asistencia',
    'name_es_ES': 'Partes de trabajo',
    'name_fr_FR': 'Feuille de présence',
    'version': '1.8.1',
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
    'description_de_DE': '''Zeiterfassungsmodul mit:
    - Aufgaben
    - Zeitpositionen

Zugehörige Berichte:
    - Stunden pro Aufgabe
    - Stunden pro Mitarbeiter pro Woche
    - Stunden pro Mitarbeiter pro Monat
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
    - Trabajo
    - Línea de parte parte de trabajo

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
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
