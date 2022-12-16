# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    gift_card_account_expense = fields.MultiValue(fields.Many2One(
            'account.account', "Gift Card Expense",
            domain=[
                ('type.gift_card', '=', True),
                ('closed', '!=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))
    gift_card_account_revenue = fields.MultiValue(fields.Many2One(
            'account.account', "Gift Card Revenue",
            domain=[
                ('type.gift_card', '=', True),
                ('closed', '!=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'gift_card_account_expense', 'gift_card_account_revenue'}:
            return pool.get('account.configuration.gift_card_account')
        return super().multivalue_model(field)


class ConfigurationGiftCardAccount(ModelSQL, CompanyValueMixin):
    "Account Configuration Gift Card Account"
    __name__ = 'account.configuration.gift_card_account'

    gift_card_account_expense = fields.Many2One(
        'account.account', "Gift Card Expense",
        domain=[
            ('type.gift_card', '=', True),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ])
    gift_card_account_revenue = fields.Many2One(
        'account.account', "Gift Card Revenue",
        domain=[
            ('type.gift_card', '=', True),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ])


def AccountTypeMixin(template=False):

    class Mixin:
        __slots__ = ()
        gift_card = fields.Boolean(
            "Gift Card",
            domain=[
                If(Eval('statement') != 'balance',
                    ('gift_card', '=', False), ()),
                ],
            states={
                'invisible': Eval('statement') != 'balance',
                })
    if not template:
        for fname in dir(Mixin):
            field = getattr(Mixin, fname)
            if not isinstance(field, fields.Field):
                continue
            field.states['readonly'] = (
                Bool(Eval('template', -1)) & ~Eval('template_override', False))
    return Mixin


class AccountTypeTemplate(AccountTypeMixin(template=True), metaclass=PoolMeta):
    __name__ = 'account.account.type.template'

    def _get_type_value(self, type=None):
        values = super()._get_type_value(type=type)
        if not type or type.gift_card != self.gift_card:
            values['gift_card'] = self.gift_card
        return values


class AccountType(AccountTypeMixin(), metaclass=PoolMeta):
    __name__ = 'account.account.type'


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def _account_domain(cls, type_):
        domain = super(InvoiceLine, cls)._account_domain(type_)
        return domain + [('type.gift_card', '=', True)]
