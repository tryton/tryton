#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Timesheet',
    'name_de_DE': 'Zeiterfassung',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Human Resources',
    'description': '''Timesheet Module with:
    - Work
    - Timesheet line

And with reports:
    - Hours per work
    - hours per employee per week
    - hours per employee per month
''',
    'description_de_DE': '''Zeiterfassungsmodul mit:
    - Aufgaben
    - Zeitpositionen

Zugehörige Berichte:
    - Stunden pro Aufgabe
    - Stunden pro Mitarbeiter pro Woche
    - Stunden pro Mitarbeiter pro Monat
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
