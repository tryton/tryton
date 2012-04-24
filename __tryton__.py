#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project Revenue',
    'name_bg_BG': 'Приходи на проект',
    'name_ca_ES': 'Ingressos per projecte',
    'name_de_DE': 'Projekte Ertrag',
    'name_es_AR': 'Beneficio de proyecto',
    'name_es_CO': 'Ingresos por proyectos',
    'name_es_ES': 'Ingresos por proyecto',
    'name_fr_FR': 'Revenu des projets',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add product on timesheet lines.
Define allowed services for each employees.
''',
    'description_bg_BG': '''Модул Приходи на проект:
    - Позволява добавяне на продукт към редове от график.
    - Позволява задаване на позволените за всеки служител услуги.
''',
    'description_ca_ES': '''Ingressos per projecte:
    - Afegeix productes a les línies de les ordres de treball.
    - Defineix serveis permesos per cada empleat.
''',
    'description_de_DE': '''Projektmodul Ertrag:
    - Ermöglicht das Hinzufügen von Artikeln zu Zeitpositionen.
    - Ermöglicht die Definition von Dienstleistungen, die für einen Mitarbeiter verwendet werden können.
''',
    'description_es_AR': '''Beneficio de proyecto:
    - Añade productos a las líneas de los partes de trabajo.
    - Define servicios permitidos por cada empleado.
''',
    'description_es_CO': ''' - Se añade el producto a las tarjetas de registro de tiempos.
 - Se define por empleado los servicios que tiene autorizados.
''',
    'description_es_ES': '''Ingresos por proyecto:
    - Añade productos a las líneas de los partes de trabajo.
    - Define servicios permitidos por cada empleado.
''',
    'description_fr_FR': '''Ajoute le produit sur la ligne de présence.
Défini par employé quels services sont autorisés.
''',
    'depends': [
        'ir',
        'project',
        'timesheet',
        'company',
        'product',
    ],
    'xml': [
        'service.xml',
        'work.xml',
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
    ],
}
