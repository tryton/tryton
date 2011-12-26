#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account',
    'name_bg_BG': 'Фактури',
    'name_de_DE': 'Buchhaltung',
    'name_es_CO': 'Contabilidad',
    'name_es_ES': 'Contabilidad',
    'name_fr_FR': 'Comptabilité',
    'name_nl_NL': 'Boekhouden',
    'version': '2.2.2',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Financial and Accounting Module with:
    - General accounting
    - Fiscal year management
    - Taxes management
    - Journal entries
    - Reconciliation

And with reports:
    - General ledger
    - Trial balance
    - Balance sheet
    - Income statement
    - Third party balance
    - Aged balance
    - General journal
''',
    'description_bg_BG': '''Модул за сечоводтсво с:
    - Общо счетоводство
    - Управление на финансови години
    - Управление на данъци
    - Записи в дневници
    - Съгласуване

Прилежащи справки:
    - Основен дневник
    - Временен баланс
    - Баланс
    - Управление на приходи
    - Баланс на външен партньор
    - Хронологичен баланс
    - Общ дневник
''',
    'description_de_DE': '''Buchhaltungsmodul mit:
    - Allgemeiner Buchhaltung
    - Verwaltung von Geschäftsjahren
    - Verwaltung von Steuern
    - Buchführung
    - Abstimmung

Zugehörige Berichte:
    - Hauptbuch
    - Summen- und Saldenliste
    - Bilanzbogen
    - Gewinn- und Verlustrechnung
    - Offene Posten
    - Fälligkeitsliste
    - Allgemeines Journal
''',
    'description_es_CO': '''El módulo Financiero y de Contabilidad cuenta con:
    - Contabilidad General
    - Manejo de Años Fiscales
    - Administración de impuestos
    - Libros diarios
    - Conciliación

Y con los reportes:
    - Libro general
    - Balance de prueba
    - Hoja de Balance
    - Estado de Ingresos
    - Balance de Terceros
    - Saldos Vencidos
    - Diario general
''',
    'description_es_ES': '''Módulo financiero y de contabilidad con:
    - Contabilidad General
    - Gestión de ejercicios fiscales
    - Gestión de impuestos
    - Libros diarios
    - Conciliación

Y con los informes:
    - Libro mayor
    - Balance de sumas y saldos
    - Balance general
    - Estado de pérdidas y ganancias
    - Balance de un Tercero
    - Saldo Vencido
    - Libro diario
''',
    'description_fr_FR': '''Module financier et comptable avec:
    - Comptabilité générale
    - Gestion des années fiscales
    - Gestion des taxes
    - Journaux d'entrées
    - Réconciliation

Et les rapports:
    - Grand livre
    - Balance
    - Bilan
    - Compte des résultats
    - Balance des tiers
    - Balance agée
    - Journal général
''',
    'description_nl_NL': '''Financiële administratie met:
    - Boekhouding
    - Boekjaren beheer
    - Belastingen
    - Dagboeken
    - Afletteren

Met bijbehorende rapporten:
    - Grootboek
    - Proefbalans
    - Balans
    - Verlies- & winstrekening
    - Openstaande posten
    - Ouderdomsanalyse facturen
    - Algemeen dagboek
''',
    'depends': [
        'ir',
        'res',
        'company',
        'party',
        'currency',
    ],
    'xml': [
        'account.xml',
        'fiscalyear.xml',
        'period.xml',
        'journal.xml',
        'move.xml',
        'tax.xml',
        'party.xml',
    ],
    'translation': [
        'locale/bg_BG.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
