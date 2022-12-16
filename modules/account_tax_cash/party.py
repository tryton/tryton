# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    supplier_tax_group_on_cash_basis = fields.Many2Many(
        'account.tax.group.cash', 'party', 'tax_group',
        "Supplier Tax Group On Cash Basis",
        help="The tax group reported on cash basis for this supplier.")
