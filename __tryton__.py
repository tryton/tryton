# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Company',
    'name_bg_BG': 'Фирма',
    'name_ca_ES': 'Empresa',
    'name_de_DE': 'Unternehmen',
    'name_es_AR': 'Empresa',
    'name_es_CO': 'Compañía',
    'name_es_ES': 'Empresa',
    'name_fr_FR': 'Société',
    'name_nl_NL': 'Bedrijf',
    'version': '2.4.0',
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
    'description_bg_BG': ''' - Задаване на фирма и служители
 - Добавяне на основна и текуща фирма според предпочитания на потребителите
 - Добавяне на фирма при предпочитания
 - Задаване на нов анализатор на справки с фирмен горен колонтитул
 - Добавяне на шаблон на писмо за партньор
 - Възможност планировщика да работи на всяка фирма
''',
    'description_ca_ES': '''- Defineix empresa i empleats.
- Afegeix l'empresa principal i predeterminada a les preferències dels usuaris.
- Afegeix l'empresa a les propietats.
- Defineix un nou analitzador pels informes amb l'encapçalament de l'empresa.
- Afegeix una plantilla de carta a tercers.
- Fa que el planificador de tasques s'executi per empresa.
''',
    'description_de_DE': ''' - Ermöglicht die Eingabe von Umternehmen und Mitarbeitern.
 - Fügt Haupt- und aktuelles Unternehmen zu den Benutzereinstellungen hinzu.
 - Fügt das Unternehmen den Eigenschaften hinzu.
 - Ermöglicht die Definition eines neuen Berichtsanalysierers mit Unternehmen im Berichtskopf.
 - Fügt den Kontakten die Berichtsvorlage für Briefe hinzu.
 - Initialisiert die Aufgaben des Zeitplaners für jedes Unternehmen.
''',
    'description_es_AR': '''Define empresa y empleados.
 - Añade la empresa principal y predeterminada en las preferencias de los usuarios.
 - Añade empresa a las propiedades.
 - Define un nuevo analizador de informe para los informes con el encabezado de la empresa.
 - Añade una plantilla de carta en entidades.
 - Hace que el programador de tareas se ejecute por empresa.
''',
    'description_es_CO': ''' - Define compañía y empleados.
 - Añade compañía principal y predeterminada de acuerdo a preferencia de usuarios.
 - Añade compañía a las propiedades.
 - Define un nuevo reporteador para los encabezados de los reportes por compañía.
 - Añade plantilla de carta a un tercero.
 - Se ejecuta el agendador por compañía.
''',
    'description_es_ES': '''Define empresa y empleados.
 - Añade la empresa principal y predeterminada en las preferencias de los usuarios.
 - Añade la empresa a las propiedades.
 - Define un nuevo analizador para los informes con el encabezado de la empresa.
 - Añade una plantilla de carta a terceros.
 - Hace que el planificador de tareas se ejecute por empresa.
''',
    'description_fr_FR': '''Défini société et employé.
Ajoute les sociétés principale et courante dans les préférences de l'utilisateur.
Ajoute la société sur les propriétés.
Défini un nouveau moteur de rapport gérant une entête par société.
Ajoute un canva de lettre par tiers.
Lance les planificateurs sur chaque société.
''',
    'description_nl_NL': ''' - Definieert bedrijf en werknemers.
 - Voegt moederbedrijf en huidig bedrijf toe aan gebruikers voorkeuren.
 - Voegt bedrijf toe aan eigenschappen.
 - Definieert nieuwe rapport routine voor een rapport met 'bedrijfskop'.
 - Voegt briefsjabloon toe aan relatie.
 - Initieert automatisch herhalende taken voor elk bedrijf.
''',
    'description_ru_RU': '''Учет организаций и сотрудников.
 - Добавление основной и дочерних организаций
 - Добавление учетных организаций и свойств
 - Настройка отчетов для печати на фирменных бланках.
 - Добавление шаблона письма.
 - Устанавливает планировщика на работу с каждой учетной организацией.
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
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_AR.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ]
}
