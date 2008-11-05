#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Company',
    'name_de_DE': 'Unternehmen',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Generic',
    'description': '''Define company and employee.
Add main and current company on users preferences.
Add company on properties.
Define new report parser for report with company header.
Add letter template on party.
Make the cron run on each companies.
''',
    'description_de_DE': ''' - Ermöglicht die Eingabe von Umternehmen und Mitarbeitern.
 - Fügt Haupt- und aktuelles Unternehmen zu den Benutzereinstellungen hinzu.
 - Fügt das Unternehmen den Eigenschaften hinzu.
 - Ermöglicht die Definition eines neuen Berichtsanalysierers mit Unternehmen im Berichtskopf.
 - Fügt den Kontakten die Berichtsvorlage für Briefe hinzu.
 - Initialisiert die Aufgaben des Zeitplaners für jedes Unternehmen.
''',
    'depends': [
        'ir',
        'res',
        'party',
        'currency',
    ],
    'xml': [
        'company.xml',
        'cron.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ]
}
