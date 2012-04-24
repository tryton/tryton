#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    "name": "Account Invoice Line Standalone",
    "name_bg_BG": "Ред от независима фактура към сметка",
    "name_ca_ES": "Línia de factura independent",
    "name_de_DE": "Fakturierung ungebundene Rechnungsposition",
    "name_es_AR": "Línea de factura independiente",
    "name_es_CO": "Línea de factura autónoma",
    "name_es_ES": "Línea de factura independiente",
    "name_fr_FR": "Ligne de facture autonome",
    "version": "2.4.1",
    "author": "B2CK",
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    "description": '''Allow to create standalone invoice lines and add them later to a draft
invoice. The invoice will only accept invoice lines with the same
type, company, currency and party.
''',
    "description_bg_BG": '''Позволява създаване на редове от независими фактури и по-късното им добавяне
    към проект на фактура. Фактурата приема редове само с едни и същи вид, фирма, валута и партньор.
''',
    "description_ca_ES": '''Permet crear línies de factura independents i
afegir-les a una factura esborrany. La factura només acceptarà línies de factura amb
el mateix tipus, empresa, divisa i tercer.
''',
    "description_de_DE": '''Fakturierung mit ungebundenen Rechnungspositionen
    - Ermöglicht die Erstellung ungebundener Rechnungspositionen, die später zu
      Rechnungen mit Status Entwurf hinzugefügt werden können.
    - Innerhalb einer Rechnung können nur Rechnungspositionen mit
      übereinstimmendem Typ, Unternehmen, Währung und Partei verwendet werden.
''',
    "description_es_AR": '''Permite crear líneas de factura independientes y
añadirlas a una factura borrador. La factura solo aceptará líneas de factura
con el mismo tipo, empresa, divisa y entidad.
''',
    "description_es_CO": '''Permite crear líneas individuales para facturación y añadirlas
posteriormente a una factura en borrador. La factuara aceptará únicamente líneas de factura del
mismo tipo, compañía, moneda y tercero.
''',
    "description_es_ES": '''Permite crear líneas de factura independientes y
añadirlas a una factura borrador. La factura sólo aceptará líneas de factura
con el mismo tipo, empresa, divisa y tercero.
''',
    "description_fr_FR": '''Permet de créer des lignes de facture autonomes et de les ajouter
ensuite à des factures dans l'état brouillon. La facture n'acceptera
que des lignes qui ont les même type, société, devis et tiers.
''',
    "depends": [
        "ir",
        "account_invoice",
    ],
    "xml": [
        "invoice.xml",
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
