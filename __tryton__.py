#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account French',
    'name_ca_ES': 'Comptabilitat francesa',
    'name_de_DE': 'Französischer Kontenrahmen',
    'name_fr_FR': 'Comptabilité française',
    'name_es_ES': 'Contabilidad francesa',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Define an account chart template for French.
Usefull to create a French account chart with the wizard in
"Financial Management>Configuration>General Account>Create Chart of Account from Template".
''',
    'description_ca_ES': '''Defineix una plantilla de pla comptable francès.
Permet crear un pla comptable francès amb l'assistent
"Comptabilitat>Configuració>Plans comptables>Crea pla comptable des de plantilla".
''',
    'description_de_DE': '''Kontenrahmenvorlage für Frankreich
    - Ermöglicht die Erstellung eines französischen Kontenrahmens mit dem
    Assistenten "Buchhaltung > Einstellungen > Allgemein > Kontenrahmen von Vorlage
    erstellen"
''',
    'description_fr_FR': '''Défini le plan comptable pour la France.
''',
    'description_es_ES': '''Define una plantilla del plan contable francés.
Permite crear un plan contable francés con el asistente del menú
"Contabilidad>Configuración>Planes contables>Crear plan contable desde plantilla".
''',
    'depends': [
        'account',
    ],
    'xml': [
        'account_fr.xml',
        'tax_fr.xml',
    ],
}
