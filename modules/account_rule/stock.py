# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def _get_supplier_invoice_line_consignment(self):
        transaction = Transaction()
        context = transaction.context
        invoice_line = super()._get_supplier_invoice_line_consignment()
        taxes = [t.id for t in invoice_line.taxes]
        if set(context.get('taxes') or []) != set(taxes):
            with transaction.set_context(taxes=taxes):
                invoice_line = self._get_supplier_invoice_line_consignment()
        return invoice_line

    def _get_customer_invoice_line_consignment(self):
        transaction = Transaction()
        context = transaction.context
        invoice_line = super()._get_customer_invoice_line_consignment()
        taxes = [t.id for t in invoice_line.taxes]
        if set(context.get('taxes') or []) != set(taxes):
            with transaction.set_context(taxes=taxes):
                invoice_line = self._get_customer_invoice_line_consignment()
        return invoice_line

    def _get_account_stock_move_lines(self, type_):
        warehouse = self.warehouse
        with Transaction().set_context(
                warehouse=warehouse.id if warehouse else None):
            return super()._get_account_stock_move_lines(type_)

    def _get_account_stock_move_line(self, amount):
        warehouse = self.warehouse
        with Transaction().set_context(
                warehouse=warehouse.id if warehouse else None):
            return super()._get_account_stock_move_line(amount)
