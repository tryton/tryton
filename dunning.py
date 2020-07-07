# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from operator import attrgetter
from itertools import groupby, chain

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.wizard import StateReport
from trytond.modules.company import CompanyReport
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.tools import grouped_slice


class Level(metaclass=PoolMeta):
    __name__ = 'account.dunning.level'
    print_on_letter = fields.Boolean('Print on Letter')


class ProcessDunning(metaclass=PoolMeta):
    __name__ = 'account.dunning.process'
    print_letter = StateReport('account.dunning.letter')

    @classmethod
    def __setup__(cls):
        super(ProcessDunning, cls).__setup__()
        cls._actions.append('print_letter')

    def do_print_letter(self, action):
        dunnings = self.records
        ids = [d.id for d in dunnings
            if d.state == 'waiting'
            and not d.blocked
            and d.party
            and d.level.print_on_letter]
        if ids:
            return action, {
                'id': ids[0],
                'ids': ids,
                }

    def transition_print_letter(self):
        return self.next_state('print_letter')


class Letter(CompanyReport, metaclass=PoolMeta):
    __name__ = 'account.dunning.letter'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(Letter, cls).execute(ids, data)

    @classmethod
    def get_context(cls, records, data):
        report_context = super(Letter, cls).get_context(records, data)

        pool = Pool()
        Date = pool.get('ir.date')

        dunnings = [d for d in records
            if d.state == 'waiting'
            and not d.blocked
            and d.party]
        parties = list(set((d.party for d in dunnings)))
        payments = cls.get_pending_payments(parties)
        key = attrgetter('party')
        dunnings.sort(key=key)
        dunnings = groupby(dunnings, key)

        PartyLetter = cls.get_party_letter()
        letters = {}
        for party, current_dunnings in dunnings:
            current_dunnings = list(current_dunnings)
            dunning_amount = sum((d.amount for d in current_dunnings))
            current_payments = list(payments.get(party, []))
            payment_amount = sum((l.credit - l.debit
                    for l in current_payments))
            if dunning_amount <= payment_amount:
                continue
            letters[party] = PartyLetter(dunnings=current_dunnings,
                payments=current_payments)
        report_context['letters'] = letters
        report_context['today'] = Date.today()
        report_context['get_payment_amount'] = cls.get_payment_amount
        report_context['get_payment_currency'] = cls.get_payment_currency
        return report_context

    @staticmethod
    def get_party_letter():

        class PartyLetter(object, metaclass=PoolMeta):
            __slots__ = ('dunnings', 'payments')

            def __init__(self, dunnings, payments):
                self.dunnings = dunnings
                self.payments = payments

            @property
            def fees(self):
                return {}

            def highest_levels(self):
                'Yield each procedure and the highest level'
                key = attrgetter('procedure')
                dunnings = sorted(self.dunnings, key=key)
                for procedure, dunnings in groupby(dunnings, key):
                    i = 0
                    for dunning in dunnings:
                        i = max(i, procedure.levels.index(dunning.level))
                    yield procedure, procedure.levels[i]

        return PartyLetter

    @staticmethod
    def get_pending_payments(parties):
        """
        Return a dictionary with party as key and the list of pending payments
        as value.
        """
        pool = Pool()
        Line = pool.get('account.move.line')
        payments = []
        for sub_parties in grouped_slice(parties):
            payments.append(Line.search([
                        ('account.type.receivable', '=', True),
                        ['OR',
                            ('debit', '<', 0),
                            ('credit', '>', 0),
                            ],
                        ('party', 'in', [p.id for p in sub_parties]),
                        ('reconciliation', '=', None),
                        ],
                    order=[('party', 'ASC'), ('id', 'ASC')]))
        payments = list(chain(*payments))
        return dict((party, list(payments))
            for party, payments in groupby(payments, attrgetter('party')))

    @staticmethod
    def get_payment_amount(payment):
        if payment.amount_second_currency:
            return -payment.amount_second_currency
        else:
            return payment.credit - payment.debit

    @staticmethod
    def get_payment_currency(payment):
        if payment.second_currency:
            return payment.second_currency
        else:
            return payment.account.company.currency
