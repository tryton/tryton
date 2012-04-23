#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Belgium',
    'name_ca_ES': 'Comptabilitat Belga',
    'name_de_DE': 'Buchhaltung Belgien',
    'name_es_AR': 'Contabilidad Belga',
    'name_es_ES': 'Contabilidad Belga',
    'name_fr_FR': 'Comptabilité belge',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define an account chart template for Belgium.
Usefull to create a Belgium account chart with the wizard in
"Financial>Configuration>General Account>Create Chart of Account from Template".
''',
    'description_ca_ES': '''Defineix una plantilla de pla comptable per a Bèlgica.
Permet crear un pla comptable Belga amb l'assistent
"Comptabilitat>Configuració>Plans comptables>Crea pla comptable des de plantilla".
''',
    'description_de_DE': '''
    - Enthält den Kontenplan für Belgien.
''',
    'description_es_ES': '''Define una plantilla de plan contable para Bélgica.
Permite crear un plan contable Belga con el asistente
"Contabilidad>Configuración>Planes contables>Crear plan contable desde plantilla".
''',
    'description_fr_FR': '''Défini le plan comptable pour la Belgique.
''',
    'depends': [
        'account',
    ],
    'xml': [
        'account_be.xml',
        'tax_be.xml',
    ],
}
