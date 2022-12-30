# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Move = pool.get('account.move')
        transaction = Transaction()
        if transaction.user and transaction.check_access:
            actions = iter(args)
            for companies, values in zip(actions, actions):
                if 'currency' in values:
                    moves = Move.search([
                            ('company', 'in', [c.id for c in companies]),
                            ],
                        limit=1, order=[])
                    if moves:
                        raise AccessError(gettext(
                                'account.msg_company_change_currency'))

        super().write(*args)
