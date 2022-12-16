# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import functools

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If, Bool


def no_payment(error):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(cls, sales, *args, **kwargs):
            for sale in sales:
                if not all((p.state == 'failed' for p in sale.payments)):
                    raise AccessError(gettext(error, sale=sale.rec_name))
            return func(cls, sales, *args, **kwargs)
        return wrapper
    return decorator


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'
    payments = fields.One2Many(
        'account.payment', 'origin', "Payments",
        domain=[
            ('company', '=', Eval('company', -1)),
            If(Eval('total_amount', 0) >= 0,
                ('kind', '=', 'receivable'),
                ('kind', '=', 'payable'),
                ),
            ('party', '=', If(Bool(Eval('invoice_party')),
                    Eval('invoice_party'), Eval('party'))),
            ('currency', '=', Eval('currency')),
            ],
        states={
            'readonly': Eval('state') != 'quotation',
            },
        depends=['company', 'total_amount', 'party', 'invoice_party',
            'currency', 'state'])

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @no_payment('sale_payment.msg_sale_cancel_payment')
    def cancel(cls, sales):
        super(Sale, cls).cancel(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @no_payment('sale_payment.msg_sale_draft_payment')
    def draft(cls, sales):
        super(Sale, cls).draft(sales)

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('payments', None)
        return super(Sale, cls).copy(sales, default=default)

    @classmethod
    def payment_confirm(cls, sales):
        "Confirm the sale based on payment authorization"
        to_confirm = []
        for sale in sales:
            payment_amount = sum(
                p.amount for p in sale.payments if p.is_authorized)
            if payment_amount >= sale.total_amount:
                to_confirm.append(sale)
        if to_confirm:
            to_confirm = cls.browse(to_confirm)  # optimize cache
            cls.confirm(to_confirm)
