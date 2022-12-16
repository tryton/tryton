# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Bool, Eval

__all__ = ['TaxCodeTemplate', 'TaxCode']


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
