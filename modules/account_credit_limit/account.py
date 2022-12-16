# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.modules.company.model import CompanyValueMixin

default_credit_limit_amount = fields.Numeric(
    "Default Credit Limit Amount",
    help="The default credit limit amount for new customers.",
    digits=(16, Eval('default_credit_limit_amount_digits', 2)),
    depends=['default_credit_limit_amount_digits'])


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    default_credit_limit_amount = fields.MultiValue(
        default_credit_limit_amount)
    default_credit_limit_amount_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_default_credit_limit_amount_digits')

    def get_default_credit_limit_amount_digits(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            return company.currency.digits


class ConfigurationDefaultCreditLimitAmount(ModelSQL, CompanyValueMixin):
    "Account Configuration Default Credit Limit Amount"
    __name__ = 'account.configuration.default_credit_limit_amount'
    default_credit_limit_amount = default_credit_limit_amount
    default_credit_limit_amount_digits = fields.Function(
        fields.Integer("Currency Digits"),
        'on_change_with_default_credit_limit_amount_digits')

    @fields.depends('company')
    def on_change_with_default_credit_limit_amount_digits(self, name=None):
        if self.company:
            return self.company.currency.digits


class Level(metaclass=PoolMeta):
    __name__ = 'account.dunning.level'
    credit_limit = fields.Boolean('Credit Limit',
        help='Has reached the credit limit.')
