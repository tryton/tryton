# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = ['Configuration']


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
