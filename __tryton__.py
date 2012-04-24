#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Sales Leads and Opportunities',
    'name_bg_BG': 'Инициативи и възможности за продажба',
    'name_ca_ES': 'Iniciatives i oportunitats comercials',
    'name_de_DE': 'Verkauf Interessenten und Chancen',
    'name_es_AR': 'Ventas: Iniciativas y Oportunidades',
    'name_es_ES': 'Iniciativas y oportunidades comerciales',
    'name_fr_FR': 'Contacts commerciaux et opportunités de ventes',
    'version': '2.4.0',
    'author': 'Sharoon Thomas, Openlabs',
    'email': 'info@openlabs.co.in',
    'website': 'http://www.openlabs.co.in/',
    'description': '''Provides:
    - Leads
    - Leads to Opportunities conversion
    - Conversion Management
    - Record of lost leads
    - Opportunities to sale orders
''',
    'description_bg_BG': '''Дава възможност за:
    - Инициативи
    - Превръшане на инициативи във възможности
    - Запис на неосъществени инициативи
    - Превръщане на възможности в поръчки за продажба
''',
    'description_ca_ES': '''Aquest mòdul permet la gestió de:
    - Iniciatives comercials
    - Conversió d'iniciatives a oportunitats
    - Gestió de les conversions
    - Registre d'iniciatives perdudes
    - Oportunitats a comandes de venda
''',
    'description_de_DE': '''Ermöglicht:
    - die Anlage von Interessenten (Leads)
    - die Umwandlung von Interessenten zu Verkaufschancen (Opportunities)
    - die Umwandlung von Chancen zu Verkäufen
    - die Verfolgung von Interessentenverlusten
''',
    'description_es_AR': '''Provee:
    - Iniciativas comerciales
    - Conversión de iniciativas a oportunidades
    - Gestión de conversiones
    - Registro de iniciativas perdidas
    - Oportunidades a órdenes de venta
''',
    'description_es_ES': '''Este módulo permite la gestión de:
    - Iniciativas comerciales
    - Conversión de iniciativas a oportunidades
    - Gestión de las conversiones
    - Registro de iniciativas perdidas
    - Oportunidades a pedidos de venta
''',
    'description_fr_FR': '''Fourni :
- Contacts commerciaux
- Conversion des contacts commerciaux en opportunités
- Gestion des conversions
- Enregistrement des contacts commerciaux perdus
- Conversion des opportunités en ordres de ventes.
''',
    'depends': [
        'party',
        'company',
        'product',
        'sale',
        'account',
        'stock',
        'currency',
    ],
    'xml': [
        'opportunity.xml',
        'party.xml',
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
