# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.extend([
                ('account.payment.braintree.customer|braintree_create',
                    "Create Braintree Customer"),
                ('account.payment.braintree.customer|braintree_delete',
                    "Delete Braintree Customer"),
                ('account.payment|braintree_transact',
                    "Transact Braintree Payment"),
                ('account.payment|braintree_pull',
                    "Pull Braintree Payment"),
                ('account.payment.braintree.refund|braintree_refund',
                    "Refund Braintree Payment"),
                ('account.payment.braintree.refund|braintree_pull',
                    "Pull Braintree Refund"),
                ])
