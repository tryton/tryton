#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Account Invoice',
    'name_bg_BG': 'Фактуриране',
    'name_ca_ES': 'Facturació',
    'name_de_DE': 'Fakturierung',
    'name_es_AR': 'Facturación',
    'name_es_CO': 'Facturación',
    'name_es_ES': 'Facturación',
    'name_fr_FR': 'Facturation',
    'name_nl_NL': 'Facturatie',
    'version': '2.4.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Financial and Accounting Module with:
    - Payment Term
    - Invoice / Credit Note
    - Supplier Invoice / Supplier Credit Note

With the possibilities:
    - to follow the payment of the invoices.
    - to define invoice sequences on fiscal year or period.
    - to credit any invoice.
''',
    'description_bg_BG': '''Финансов и счетоводен модул с:
    - Условия за плащане
    - Фактура / Кредитно известие
    - Фактура за доставчик / Кредитно известие за доставчик

Има следните възможности:
    - проследяване на плащания на фактури
    - задаване на последователности на фактура за финансова година или период
    - кредитиране на всяка фактура
''',
    'description_ca_ES': '''Mòdul financer i comptable amb:
    - Terminis de pagament
    - Factura / Abonament
    - Factura de proveïdor / Abonament de proveïdor

Amb les possibilitats de:
    - Fer el seguiment del pagament de factures.
    - Definir seqüències de factures per exercici fiscal o període.
    - Abonar qualsevol factura.
''',
    'description_de_DE': '''Modul für Buchhaltung und Fakturierung mit:
    - Definition von Zahlungsbedingungen
    - Erstellung von Rechnungen und Gutschriften für Kunden
    - Erstellung von Rechnungen und Gutschriften für Lieferanten

Ermöglicht:
    - die Verfolgung der Bezahlung von Rechnungen
    - die Definition von Rechnungssequenzen für das Geschäftsjahr bzw. die Buchungszeiträume
    - die Erstellung von Gutschriften zu jeglicher Rechnung
''',
    'description_es_AR': '''Módulo financiero y de contabilidad con:
    - Plazos de Pago
    - Factura / Nota de crédito
    - Factura de proveedor / Nota de crédito de proveedor

Con las posibilidades de:
    - hacer seguimientos del pago de facturas.
    - definir secuencias de facturas por ejercicio fiscal o período.
    - pagar cualquier factura.
''',
    'description_es_CO': '''Módulo Financiero y de Contabilidad con:
    - Términos de Pago
    - Notas de Facturación / Crédito
    - Factura de Proveedores / Nota de Crédito de Proveedores

Con las posibilidades de:
    - Hacer seguimiento al pago de facturas.
    - Definir secuencias de facturas en año o período fiscal.
    - Acreditar una factura.
''',
    'description_es_ES': '''Módulo financiero y contable con:
    - Plazos de pago
    - Factura / Abono
    - Factura de proveedor / Abono de proveedor

Con las posibilidades de:
    - Hacer el seguimiento del pago de facturas.
    - Definir secuencias de facturas por ejercicio fiscal o período.
    - Abonar cualquier factura.
''',
    'description_fr_FR': '''Module financier et comptable avec:
    - Condition de paiement
    - Facture / Note de crédit
    - Facture fournisseur / Note de crédit fournisseur

Avec la possibilité:
    - de suivre le paiment des factures
    - de définir les numérotations de facture par période ou par année fiscale
    - de créditer n'importe quelle facture

''',
    'description_nl_NL': '''Module voor facturering met:
    - Betalingstermijnen
    - Verkoopfacturen / Credit verkoopnota's
    - Inkoopfacturen / Credit inkoopnota's

Met de mogelijkheid tot:
    - het volgen van betalingen.
    - het definiëren van factuurreeksen per boekjaar.
    - het crediteren van een factuur.

''',
    'depends': [
        'ir',
        'account',
        'company',
        'party',
        'product',
        'res',
        'currency',
        'account_product',
    ],
    'xml': [
        'invoice.xml',
        'payment_term.xml',
        'party.xml',
        'account.xml',
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
