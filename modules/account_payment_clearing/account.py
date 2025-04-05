# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        models = super()._get_origin()
        return models + ['account.payment']


def _payments_to_update(reconciliations):
    pool = Pool()
    Payment = pool.get('account.payment')
    Reconciliation = pool.get('account.move.reconciliation')

    moves = set()
    others = set()
    for reconciliation in reconciliations:
        for line in reconciliation.lines:
            moves.add(line.move)
            others.update(line.reconciliations_delegated)

    payments = set()
    for sub_moves in grouped_slice(moves):
        payments.update(Payment.search([
                    ('clearing_move', 'in', [m.id for m in sub_moves]),
                    ], order=[]))
    if others:
        payments.update(_payments_to_update(Reconciliation.browse(others)))

    return payments


class MoveReconciliation(metaclass=PoolMeta):
    __name__ = 'account.move.reconciliation'

    @classmethod
    def on_modification(cls, mode, reconciliations, field_names=None):
        pool = Pool()
        Payment = pool.get('account.payment')
        super().on_modification(mode, reconciliations, field_names=field_names)
        Payment.__queue__.update_reconciled(
            list(_payments_to_update(reconciliations)))
