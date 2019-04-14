# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Bool, Eval

__all__ = ['TaxCodeTemplate', 'TaxCode', 'TaxTemplate', 'Tax']


class TaxCodeTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.code.template'

    aeat_report = fields.Selection([
            (None, ''),
            ('111', "Model 111"),
            ('115', "Model 115"),
            ('303', "Model 303"),
            ], "AEAT Report")

    def _get_tax_code_value(self, code=None):
        value = super(TaxCodeTemplate, self)._get_tax_code_value(code=code)
        value['aeat_report'] = self.aeat_report
        return value


class TaxCode(metaclass=PoolMeta):
    __name__ = 'account.tax.code'

    aeat_report = fields.Selection([
            (None, ''),
            ('111', "Model 111"),
            ('115', "Model 115"),
            ('303', "Model 303"),
            ], "AEAT Report",
        states={
            'readonly': (Bool(Eval('template', -1))
                & ~Eval('template_override', False)),
            },
        depends=['template', 'template_override'])


class TaxTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    es_vat_list_code = fields.Char("Spanish VAT List Code")
    es_ec_purchases_list_code = fields.Char("Spanish EC Purchase List Code")

    def _get_tax_value(self, tax=None):
        value = super()._get_tax_value(tax=tax)
        for name in ['es_vat_list_code', 'es_ec_purchases_list_code']:
            if not tax or getattr(tax, name) != getattr(self, name):
                value[name] = getattr(self, name)
        return value


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    es_vat_list_code = fields.Char("Spanish VAT List Code",
        states={
            'readonly': (Bool(Eval('template', -1))
                & ~Eval('template_override', False)),
            },
        depends=['template', 'template_override'])
    es_ec_purchases_list_code = fields.Char("Spanish EC Purchases List Code",
        states={
            'readonly': (Bool(Eval('template', -1))
                & ~Eval('template_override', False)),
            },
        depends=['template', 'template_override'])
