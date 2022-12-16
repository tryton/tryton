# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = ['Configuration', 'Level']
__metaclass__ = PoolMeta


class Configuration:
    __name__ = 'account.configuration'

    default_credit_limit_amount = fields.Function(fields.Numeric(
            'Default Credit Limit Amount',
            digits=(16, Eval('default_credit_limit_amount_digits', 2)),
            depends=['default_credit_limit_amount_digits']),
        'get_default_credit_limit_amount',
        setter='set_default_credit_limit_amount')
    default_credit_limit_amount_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_default_credit_limit_amount_digits')

    def get_default_credit_limit_amount(self, name):
        pool = Pool()
        Property = pool.get('ir.property')
        ModelField = pool.get('ir.model.field')
        company_id = Transaction().context.get('company')
        field, = ModelField.search([
                ('model.model', '=', 'party.party'),
                ('name', '=', name[8:]),
                ], limit=1)
        properties = Property.search([
                ('field', '=', field.id),
                ('res', '=', None),
                ('company', '=', company_id),
                ], limit=1)
        if properties:
            prop, = properties
            return Decimal(prop.value.split(',')[1])

    @classmethod
    def set_default_credit_limit_amount(cls, configurations, name, value):
        pool = Pool()
        Property = pool.get('ir.property')
        ModelField = pool.get('ir.model.field')
        company_id = Transaction().context.get('company')
        field, = ModelField.search([
                ('model.model', '=', 'party.party'),
                ('name', '=', name[8:]),
                ], limit=1)
        properties = Property.search([
                ('field', '=', field.id),
                ('res', '=', None),
                ('company', '=', company_id),
                ])
        Property.delete(properties)
        if value:
            Property.create([{
                        'field': field.id,
                        'value': ',%s' % value,
                        'company': company_id,
                        }])

    def get_default_credit_limit_amount_digits(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if not company_id:
            return 2
        company = Company(company_id)
        return company.currency.digits


class Level:
    __name__ = 'account.dunning.level'
    credit_limit = fields.Boolean('Credit Limit',
        help='Has reached the credit limit')
