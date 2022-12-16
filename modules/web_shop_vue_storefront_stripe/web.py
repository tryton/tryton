# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval


class Shop(metaclass=PoolMeta):
    __name__ = 'web.shop'

    stripe_journal = fields.Many2One(
        'account.payment.journal', "Stripe Journal",
        domain=[
            ('stripe_account', '!=', None),
            ('currency', '=', Eval('currency', -1)),
            ],
        depends=['currency'])

    def vsf_order_create(self, data, sale, user):
        pool = Pool()
        Payment = pool.get('account.payment')
        PaymentGroup = pool.get('account.payment.group')
        sale = super().vsf_order_create(data, sale, user)
        payment_method = data['addressInformation']['payment_method_code']
        if payment_method == 'stripe':
            payment_method_additional = (
                data['addressInformation']['payment_method_additional'])
            payment = Payment()
            payment.company = sale.company
            payment.kind = 'receivable'
            payment.party = sale.party
            payment.origin = sale
            payment.amount = sale.total_amount
            payment.journal = self.stripe_journal
            payment.stripe_token = payment_method_additional['id']
            payment.stripe_chargeable = True
            payment.save()
            Payment.approve([payment])
            group = PaymentGroup(
                company=payment.company,
                journal=payment.journal,
                kind=payment.kind)
            group.save()
            Payment.process([payment], lambda: group)
        return sale
