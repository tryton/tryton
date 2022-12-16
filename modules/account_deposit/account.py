# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import If, Eval, Bool


def AccountTypeMixin(template=False):

    class Mixin:
        __slots__ = ()
        deposit = fields.Boolean(
            "Deposit",
            domain=[
                If(~Eval('statement').in_(['off-balance', 'balance']),
                    ('deposit', '=', False), ()),
                ],
            states={
                'invisible': ~Eval('statement').in_(
                    ['off-balance', 'balance']),
                },
            depends=['statement'])
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
        if not type or type.deposit != self.deposit:
            values['deposit'] = self.deposit
        return values


class AccountType(AccountTypeMixin(), metaclass=PoolMeta):
    __name__ = 'account.account.type'


class Reconcile(metaclass=PoolMeta):
    __name__ = 'account.reconcile'

    def get_parties(self, account, _balanced=False, party=None):
        if account.type.deposit:
            _balanced = True
        return super().get_parties(account, _balanced=_balanced, party=party)
