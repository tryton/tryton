# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval


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
    es_reported_with = fields.Many2One('account.tax.template', "Reported With")

    def _get_tax_value(self, tax=None):
        value = super()._get_tax_value(tax=tax)
        for name in ['es_vat_list_code', 'es_ec_purchases_list_code']:
            if not tax or getattr(tax, name) != getattr(self, name):
                value[name] = getattr(self, name)
        return value

    @classmethod
    def create_tax(
            cls, account_id, company_id, template2account, template2tax=None):
        pool = Pool()
        Tax = pool.get('account.tax')
        super().create_tax(
            account_id, company_id, template2account, template2tax)

        to_write = []

        for template_id, tax_id in template2tax.items():
            template = cls(template_id)
            if not template.es_reported_with:
                continue
            reported_with = template2tax[template.es_reported_with.id]
            to_write.append([Tax(tax_id)])
            to_write.append({
                    'es_reported_with': reported_with,
                    })

        if to_write:
            Tax.write(*to_write)


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
    es_reported_with = fields.Many2One('account.tax', "Reported with",
        states={
            'readonly': (Bool(Eval('template', -1))
                & ~Eval('template_override', False)),
            },
        depends=['template', 'template_override'])

    @classmethod
    def update_tax(cls, company_id, template2account, template2tax=None):
        super().update_tax(company_id, template2account, template2tax)

        to_write = []

        for template_id, tax_id in template2tax.items():
            tax = cls(tax_id)
            if not tax.template_override:
                values = {}
                reported_with = (tax.es_reported_with.id
                    if tax.es_reported_with else None)
                if (tax.template.es_reported_with
                        and reported_with != template2tax.get(
                                tax.template.es_reported_with.id)):
                    values['es_reported_with'] = template2tax.get(
                        tax.template.es_reported_with.id)
                elif (not tax.template.es_reported_with
                        and tax.es_reported_with):
                    values['es_reported_with'] = None
                if values:
                    to_write.append([tax])
                    to_write.append(values)

        if to_write:
            cls.write(*to_write)
