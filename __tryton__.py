#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project Revenue',
    'name_de_DE': 'Projekte Ertrag',
    'name_es_CO': 'Ingresos por proyectos',
    'name_es_ES': 'Beneficio de proyecto',
    'name_fr_FR': 'Revenu des projets',
    'version': '1.8.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add product on timesheet lines.
Define allowed services for each employees.
''',
    'description_de_DE': '''Projektmodul Ertrag:
    - Ermöglicht das Hinzufügen von Artikeln zu Zeitpositionen.
    - Ermöglicht die Definition von Dienstleistungen, die für einen Mitarbeiter verwendet werden können.
''',
    'description_es_CO':''' - Se añade el producto a las tarjetas de registro de tiempos.
 - Se define por empleado los servicios que tiene autorizados.
''',
    'description_es_ES':'''Beneficio de proyecto:
    - Añade productos a las líneas de los partes de trabajo.
    - Define servicios permitidos por cada empleado.
''',
    'description_fr_FR':'''Ajoute le produit sur la ligne de présence.
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
        'de_DE.csv',
        'es_CO.csv',
        'es_ES.csv',
        'fr_FR.csv',
    ],
}
