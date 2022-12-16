# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    purchase_taxes_expense = fields.Boolean(
        "Purchase Taxes as Expense",
        help="Check to book purchase taxes as expense.")
    cancel_invoice_out = fields.Boolean(
        "Cancel Customer Invoice",
        help="Allow cancelling move of customer invoice.")

    @classmethod
    def default_purchase_taxes_expense(cls):
        return False

    @classmethod
    def default_cancel_invoice_out(cls):
        return False
