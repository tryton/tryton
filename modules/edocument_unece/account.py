# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    unece_code = fields.Selection([
            (None, ''),
            ('AAA', "Petroleum tax"),
            ('AAB', "Provisional countervailing duty cash"),
            ('AAC', "Provisional countervailing duty bond"),
            ('AAD', "Tobacco tax"),
            ('AAE', "Energy fee"),
            ('AAF', "Coffee tax"),
            ('AAG', "Harmonised sales tax, Canadian"),
            ('AAH', "Quebec sales tax"),
            ('AAI', "Canadian provincial sales tax"),
            ('AAJ', "Tax on replacement part"),
            ('AAK', "Mineral oil tax"),
            ('AAL', "Special tax"),
            ('AAM', "Insurance tax"),
            ('ADD', "Anti-dumping duty"),
            ('BOL', "Stamp duty (Imposta di Bollo)"),
            ('CAP', "Agricultural levy"),
            ('CAR', "Car tax"),
            ('COC', "Paper consortium tax (Italy)"),
            ('CST', "Commodity specific tax"),
            ('CUD', "Customs duty"),
            ('CVD', "Countervailing duty"),
            ('ENV', "Environmental tax"),
            ('EXC', "Excise duty"),
            ('EXP', "Agricultural export rebate"),
            ('FET', "Federal excise tax"),
            ('FRE', "Free"),
            ('GCN', "General construction tax"),
            ('GST', "Goods and services tax"),
            ('ILL', "Illuminants tax"),
            ('IMP', "Import tax"),
            ('IND', "Individual tax"),
            ('LAC', "Business license fee"),
            ('LCN', "Local construction tax"),
            ('LDP', "Light dues payable"),
            ('LOC', "Local sales tax"),
            ('LST', "Lust tax"),
            ('MCA', "Monetary compensatory amount"),
            ('MCD', "Miscellaneous cash deposit"),
            ('OTH', "Other taxes"),
            ('PDB', "Provisional duty bond"),
            ('PDC', "Provisional duty cash"),
            ('PRF', "Preference duty"),
            ('SCN', "Special construction tax"),
            ('SSS', "Shifted social securities"),
            ('STT', "State/provincial sales tax"),
            ('SUP', "Suspended duty"),
            ('SUR', "Surtax"),
            ('SWT', "Shifted wage tax"),
            ('TAC', "Alcohol mark tax"),
            ('TOT', "Total"),
            ('TOX', "Turnover tax"),
            ('TTA', "Tonnage taxes"),
            ('VAD', "Valuation deposit"),
            ('VAT', "Value added tax"),
            ], "UNECE Code",
        states={
            'readonly': (Bool(Eval('template', -1))
                & ~Eval('template_override', False)),
            },
        help="Standard code of "
        "the United Nations Economic Commission for Europe.")
    unece_category_code = fields.Selection([
            (None, ''),
            ('A', "Mixed tax rate"),
            ('AA', "Lower rate"),
            ('AB', "Exempt for resale"),
            ('AC', "Value Added Tax (VAT) not now due for payment"),
            ('AD', "Value Added Tax (VAT) due from a previous invoice"),
            ('AE', "VAT Reverse Charge"),
            ('B', "Transferred (VAT)"),
            ('C', "Duty paid by supplier"),
            ('D', "Value Added Tax (VAT) margin scheme - travel agents"),
            ('E', "Exempt from tax"),
            ('F', "Value Added Tax (VAT) margin scheme - second-hand goods"),
            ('G', "Free export item, tax not charged"),
            ('H', "Higher rate"),
            ('I', "Value Added Tax (VAT) margin scheme - works of art"),
            ('J', "Value Added Tax (VAT) margin scheme - "
                "collector's items and antiques"),
            ('K', "VAT exempt for EEA intra-community supply of "
                "goods and services"),
            ('L', "Canary Islands general indirect tax"),
            ('M', "Tax for production, services and importation in "
                "Ceuta and Melilla"),
            ('O', "Services outside scope of tax"),
            ('S', "Standard rate"),
            ('Z', "Zero rated goods"),
            ], "UNECE Category Code",
        states={
            'readonly': (Bool(Eval('template', -1))
                & ~Eval('template_override', False)),
            },
        help="Standard code of "
        "the United Nations Economic Commission for Europe.")


class TaxTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    unece_code = fields.Selection('get_unece_codes', "UNECE Code")
    unece_category_code = fields.Selection(
        'get_unece_category_code', "UNECE Category Code")

    @classmethod
    def get_unece_codes(cls):
        pool = Pool()
        Tax = pool.get('account.tax')
        return Tax.fields_get(['unece_code'])['unece_code']['selection']

    @classmethod
    def get_unece_category_code(cls):
        pool = Pool()
        Tax = pool.get('account.tax')
        return Tax.fields_get(
            ['unece_category_code'])['unece_category_code']['selection']

    def _get_tax_value(self, tax=None):
        value = super(TaxTemplate, self)._get_tax_value(tax=tax)
        for field in ['unece_code', 'unece_category_code']:
            if not tax or getattr(tax, field) != getattr(self, field):
                value[field] = getattr(self, field)
        return value
