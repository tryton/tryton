# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    supplier_tax_group_on_cash_basis = fields.Many2Many(
        'account.tax.group.cash', 'party', 'tax_group',
        "Supplier Tax Group On Cash Basis",
        help="The tax group reported on cash basis for this supplier.")

    @classmethod
    def copy(cls, parties, default=None):
        context = Transaction().context
        default = default.copy() if default else {}
        if context.get('_check_access'):
            default.setdefault(
                'supplier_tax_group_on_cash_basis',
                cls.default_get(
                    ['supplier_tax_group_on_cash_basis'],
                    with_rec_name=False).get(
                    'supplier_tax_group_on_cash_basis'))
        return super().copy(parties, default=default)
