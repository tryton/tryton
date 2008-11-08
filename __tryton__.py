#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project Revenue',
    'name_de_DE': 'Projekte Ertrag',
    'name_fr_FR': 'Revenu des projets',
    'name_es_ES': 'Ingresos por proyectos',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Add product on timesheet lines.
Define allowed services for each employees.
''',
    'description_de_DE': ''' - Ermöglicht das Hinzufügen von Artikeln zu Zeitpositionen.
 - Ermöglicht die Definition von Dienstleistungen, die für einen Mitarbeiter verwendet werden können.
''',
    'description_fr_FR':'''Ajoute le produit sur la ligne de présence.
Défini par employé quels services sont autorisés.
''',
    'description_es_ES':''' - Se añade el producto a las tarjetas de registro de tiempos.
 - Se define por empleado los servicios que tiene autorizados.
''',
    'depends': [
        'ir',
        'project',
        'company',
        'product',
    ],
    'xml': [
        'service.xml',
        'timesheet.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
