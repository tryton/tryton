# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.extend([
                ('account.payment|stripe_charge', "Charge Stripe Payments"),
                ('account.payment|stripe_capture_', "Capture Stripe Payments"),
                ('account.payment.stripe.refund|stripe_create',
                    "Create Stripe Refund"),
                ('account.payment.stripe.customer|stripe_create',
                    "Create Stripe Customer"),
                ('account.payment.stripe.customer|stripe_intent_update',
                    "Update Stripe Intent Customer"),
                ('account.payment.stripe.customer|stripe_delete',
                    "Delete Stripe Customer"),
                ('account.payment.stripe.account|fetch_events',
                    "Fetch Stripe Events"),
                ])
