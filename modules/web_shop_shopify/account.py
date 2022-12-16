# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal

from trytond.model import Unique
from trytond.pool import Pool, PoolMeta

from .common import IdentifierMixin


class Payment(IdentifierMixin, metaclass=PoolMeta):
    __name__ = 'account.payment'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('shopify_identifier_unique',
                Unique(t, t.shopify_identifier_signed),
                'web_shop_shopify.msg_identifier_payment_unique'),
            ]

    @classmethod
    def _get_shopify_payment_journal_pattern(cls, sale, transaction):
        return {
            'gateway': transaction.gateway,
            }

    @classmethod
    def _get_from_shopify(cls, sale, transaction):
        assert transaction.kind in {'authorization', 'sale'}
        payment = cls(shopify_identifier=transaction.id)
        payment.company = sale.company
        payment.journal = sale.web_shop.get_payment_journal(
            transaction.currency,
            cls._get_shopify_payment_journal_pattern(
                sale, transaction))
        payment.kind = 'receivable'
        payment.amount = Decimal(transaction.amount)
        payment.origin = sale
        payment.party = sale.party
        return payment

    @classmethod
    def get_from_shopify(cls, sale, order):
        pool = Pool()
        Group = pool.get('account.payment.group')

        id2payments = {}
        to_process = defaultdict(list)
        transactions = [
            t for t in order.transactions() if t.status == 'success']
        # Order transactions to process parent first
        kinds = ['authorization', 'capture', 'sale', 'void', 'refund']
        transactions.sort(key=lambda t: kinds.index(t.kind))
        amounts = defaultdict(Decimal)
        for transaction in transactions:
            if transaction.kind not in {'authorization', 'sale'}:
                continue
            payments = cls.search([
                    ('shopify_identifier', '=', transaction.id),
                    ])
            if payments:
                payment, = payments
            else:
                payment = cls._get_from_shopify(sale, transaction)
                to_process[payment.company, payment.journal].append(payment)
            id2payments[transaction.id] = payment
            amounts[transaction.id] = Decimal(transaction.amount)
        cls.save(list(id2payments.values()))

        for (company, journal), payments in to_process.items():
            group = Group(
                company=company,
                journal=journal,
                kind='receivable')
            group.save()
            cls.submit(payments)
            cls.process(payments, lambda: group)

        captured = defaultdict(Decimal)
        voided = defaultdict(Decimal)
        refunded = defaultdict(Decimal)
        for transaction in transactions:
            if transaction.kind == 'sale':
                payment = id2payments[transaction.id]
                captured[payment] += Decimal(transaction.amount)
            elif transaction.kind == 'capture':
                payment = id2payments[transaction.parent_id]
                id2payments[transaction.id] = payment
                captured[payment] += Decimal(transaction.amount)
            elif transaction.kind == 'void':
                payment = id2payments[transaction.parent_id]
                voided[payment] += Decimal(transaction.amount)
            elif transaction.kind == 'refund':
                payment = id2payments[transaction.parent_id]
                captured[payment] -= Decimal(transaction.amount)
                refunded[payment] += Decimal(transaction.amount)

        to_save = []
        for payment in id2payments.values():
            if captured[payment] and payment.amount != captured[payment]:
                payment.amount = captured[payment]
                to_save.append(payment)
        cls.proceed(to_save)
        cls.save(to_save)

        to_succeed, to_fail, to_proceed = set(), set(), set()
        for transaction_id, payment in id2payments.items():
            if amounts[transaction_id] == (
                    captured[payment] + voided[payment] + refunded[payment]):
                if payment.amount:
                    if payment.state != 'succeeded':
                        to_succeed.add(payment)
                else:
                    if payment.state != 'failed':
                        to_fail.add(payment)
            elif payment.state != 'processing':
                to_proceed.add(payment)
        cls.fail(to_fail)
        cls.proceed(to_proceed)
        cls.succeed(to_succeed)

        return list(id2payments.values())


class PaymentJournal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.process_method.selection.append(('shopify', "Shopify"))
