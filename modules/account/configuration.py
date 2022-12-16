# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (ModelView, ModelSQL,
            ModelSingleton, MatchMixin, fields, sequence_ordered)
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = ['Configuration', 'ConfigurationTaxRounding']

tax_roundings = [
    ('document', 'Per Document'),
    ('line', 'Per Line'),
    ]


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Account Configuration'
    __name__ = 'account.configuration'
    default_account_receivable = fields.Function(fields.Many2One(
        'account.account', 'Default Account Receivable',
        domain=[
                ('kind', '=', 'receivable'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')
    default_account_payable = fields.Function(fields.Many2One(
        'account.account', 'Default Account Payable',
        domain=[
                ('kind', '=', 'payable'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_account', setter='set_account')
    tax_rounding = fields.Function(fields.Selection(tax_roundings,
            'Tax Rounding'), 'on_change_with_tax_rounding')
    tax_roundings = fields.One2Many('account.configuration.tax_rounding',
        'configuration', 'Tax Roundings')

    @classmethod
    def default_tax_rounding(cls):
        return 'document'

    @classmethod
    def _get_account_field(cls, name):
        pool = Pool()
        ModelField = pool.get('ir.model.field')
        if name in ['default_account_receivable', 'default_account_payable']:
            field, = ModelField.search([
                ('model.model', '=', 'party.party'),
                ('name', '=', name[8:]),
                ], limit=1)
            return field

    def get_account(self, name):
        pool = Pool()
        Property = pool.get('ir.property')
        company_id = Transaction().context.get('company')
        account_field = self._get_account_field(name)
        properties = Property.search([
            ('field', '=', account_field.id),
            ('res', '=', None),
            ('company', '=', company_id),
            ], limit=1)
        if properties:
            prop, = properties
            return prop.value.id

    @classmethod
    def set_account(cls, configurations, name, value):
        pool = Pool()
        Property = pool.get('ir.property')
        company_id = Transaction().context.get('company')
        account_field = cls._get_account_field(name)
        properties = Property.search([
            ('field', '=', account_field.id),
            ('res', '=', None),
            ('company', '=', company_id),
            ])
        Property.delete(properties)
        if value:
            Property.create([{
                        'field': account_field.id,
                        'value': 'account.account,%s' % value,
                        'company': company_id,
                        }])

    @fields.depends('tax_roundings')
    def on_change_with_tax_rounding(self, name=None, pattern=None):
        context = Transaction().context
        if pattern is None:
            pattern = {}
        pattern = pattern.copy()
        pattern['company'] = context.get('company')

        for line in self.tax_roundings:
            if line.match(pattern):
                return line.method
        return self.default_tax_rounding()


class ConfigurationTaxRounding(
        sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Account Configuration Tax Rounding'
    __name__ = 'account.configuration.tax_rounding'
    configuration = fields.Many2One('account.configuration', 'Configuration',
        required=True, ondelete='CASCADE')
    company = fields.Many2One('company.company', 'Company')
    method = fields.Selection(tax_roundings, 'Method', required=True)

    @classmethod
    def default_method(cls):
        return 'document'
