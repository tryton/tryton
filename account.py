# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import functools
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If


def sale_payment_confirm(func):
    @functools.wraps(func)
    def wrapper(cls, payments, *args, **kwargs):
        pool = Pool()
        Sale = pool.get('sale.sale')

        result = func(cls, payments, *args, **kwargs)

        sales = {p.origin for p in payments
            if isinstance(p.origin, Sale)}
        sales = Sale.browse(sales)  # optimize cache
        Sale.payment_confirm(sales)

        return result
    return wrapper


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.origin.domain['sale.sale'] = [
            If(~Eval('state').in_(['failed', 'succeeded']),
                ('state', '!=', 'draft'),
                ()),
            If(Eval('state') == 'draft',
                ('state', '!=', 'cancelled'),
                ()),
            ]

    @classmethod
    def _get_origin(cls):
        return super(Payment, cls)._get_origin() + ['sale.sale']

    @fields.depends('origin')
    def on_change_origin(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        try:
            super().on_change_origin()
        except AttributeError:
            pass
        if self.origin and isinstance(self.origin, Sale):
            sale = self.origin
            party = (
                getattr(sale, 'invoice_party', None)
                or getattr(sale, 'party', None))
            if party:
                self.party = party
            sale_amount = getattr(sale, 'total_amount', None)
            payment_amount = sum(
                (p.amount for p in getattr(sale, 'payments', [])
                    if p.state != 'failed'),
                Decimal(0))
            if sale_amount is not None:
                self.kind = 'receivable' if sale_amount > 0 else 'payable'
                self.amount = abs(sale_amount) - payment_amount
            currency = getattr(sale, 'currency', None)
            if currency is not None:
                self.currency = currency

    @classmethod
    def create(cls, vlist):
        payments = super(Payment, cls).create(vlist)
        cls.trigger_authorized([p for p in payments if p.is_authorized])
        return payments

    @classmethod
    def write(cls, *args):
        payments = sum(args[0:None:2], [])
        unauthorized = {p for p in payments if not p.is_authorized}
        super(Payment, cls).write(*args)
        authorized = {p for p in payments if p.is_authorized}
        cls.trigger_authorized(cls.browse(unauthorized & authorized))

    @property
    def is_authorized(self):  # TODO: move to account_payment
        return self.state == 'succeeded'

    @classmethod
    @sale_payment_confirm
    def trigger_authorized(cls, payments):
        pass


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    def add_payments(self, payments=None):
        "Add payments from sales lines to pay"
        if payments is None:
            payments = []
        payments = set(payments)
        for sale in self.sales:
            payments.update(sale.payments)
        payments = list(payments)
        # Knapsack problem:
        # simple heuristic by trying to fill biggest amount first.
        payments.sort(key=lambda p: p.amount)
        lines_to_pay = sorted(
            self.lines_to_pay, key=lambda l: l.payment_amount)
        for line in lines_to_pay:
            if line.reconciliation:
                continue
            payment_amount = line.payment_amount
            for payment in payments:
                if payment.line or payment.state == 'failed':
                    continue
                if ((payment.kind == 'receivable' and line.credit > 0)
                        or (payment.kind == 'payable' and line.debit > 0)):
                    continue
                if payment.party != line.party:
                    continue
                if (getattr(payment, 'account')
                        and payment.account != line.account):
                    continue
                if payment.amount <= payment_amount:
                    payment.line = line
                    if hasattr(payment, 'account'):
                        payment.account = None
                    payment_amount -= payment.amount
        return payments

    def reconcile_payments(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        Line = pool.get('account.move.line')
        if not hasattr(Payment, 'clearing_move'):
            return
        to_reconcile = []
        for line in self.lines_to_pay:
            if line.reconciliation:
                continue
            lines = [line]
            for payment in line.payments:
                if payment.state == 'succeeded' and payment.clearing_move:
                    for pline in payment.clearing_move.lines:
                        if (pline.account == line.account
                                and not pline.reconciliation):
                            lines.append(pline)
            if not sum(l.debit - l.credit for l in lines):
                to_reconcile.append(lines)
        for lines in to_reconcile:
            Line.reconcile(lines)

    @classmethod
    def _post(cls, invoices):
        pool = Pool()
        Payment = pool.get('account.payment')

        super()._post(invoices)

        payments = set()
        for invoice in invoices:
            payments.update(invoice.add_payments())
        if payments:
            Payment.save(payments)
        if hasattr(Payment, 'clearing_move'):
            # Ensure clearing move is created as succeed may happen
            # before the payment has a line.
            Payment.set_clearing_move(
                [p for p in payments if p.state == 'succeeded'])
            for invoice in invoices:
                invoice.reconcile_payments()
