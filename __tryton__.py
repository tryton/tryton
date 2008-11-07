#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Timesheet',
    'name_de_DE': 'Zeiterfassung',
    'name_fr_FR': 'Feuille de présence',
    'version': '0.0.1',
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
    'description': '''Module feuille de présence, avec:
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
    ],
    'xml': [
        'timesheet.xml',
        'work.xml',
        'line.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
