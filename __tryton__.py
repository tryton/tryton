#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Company',
    'name_de_DE': 'Unternehmen',
    'name_es_CO': 'Compañía',
    'name_es_ES': 'Compañía',
    'name_fr_FR': 'Compagnie',
    'version': '1.2.4',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define company and employee.
Add main and current company on users preferences.
Add company on properties.
Define new report parser for report with company header.
Add letter template on party.
Make the scheduler run on each companies.
''',
    'description_de_DE': ''' - Ermöglicht die Eingabe von Umternehmen und Mitarbeitern.
 - Fügt Haupt- und aktuelles Unternehmen zu den Benutzereinstellungen hinzu.
 - Fügt das Unternehmen den Eigenschaften hinzu.
 - Ermöglicht die Definition eines neuen Berichtsanalysierers mit Unternehmen im Berichtskopf.
 - Fügt den Kontakten die Berichtsvorlage für Briefe hinzu.
 - Initialisiert die Aufgaben des Zeitplaners für jedes Unternehmen.
''',
    'description_es_CO': ''' - Define compañía y empleados.
 - Añade compañía principal y predeterminada de acuerdo a preferencia de usuarios.
 - Añade compañía a las propiedades.
 - Define un nuevo reporteador para los encabezados de los reportes por compañía.
 - Añade plantilla de carta a un tercero.
 - Se ejecuta el agendador por compañía.
''',
    'description_es_ES': ''' - Define compañía y empleados.
 - Añade compañía principal y predeterminada de acuerdo a preferencia de usuarios.
 - Añade compañía a las propiedades.
 - Define un nuevo reporteador para los encabezados de los reportes por compañía.
 - Añade plantilla de carta a un tercero.
 - Se ejecuta el agendador por compañía.
''',
    'description_fr_FR': '''Defini compagnie et employé.
Ajoute les compagnies principale et courante dans les préférences de l'utilisateur.
Ajoute la compagnie sur les propriétés.
Défini un nouveau moteur de rapport gérant une entête par compagnie.
Ajoute un canva de lettre par tiers.
Lance les planificateurs sur chaque compagnie.
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
        'es_CO.csv',
        'es_ES.csv',
        'de_DE.csv',
    ]
}
