# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal

from trytond.model import Unique
from trytond.pool import PoolMeta

from .common import IdentifierMixin, gid2id


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

    def process_shopify(self):
        pass

    @classmethod
    def shopify_fields(cls):
        return {
            'id': None,
            'kind': None,
            'amountSet': {
                'presentmentMoney': {
                    'amount': None,
                    'currencyCode': None,
                    },
                },
            'parentTransaction': {
                'id': None,
                },
            'gateway': None,
            'status': None,
            }

    @classmethod
    def _get_shopify_payment_journal_pattern(cls, sale, transaction):
        return {
            'gateway': transaction['gateway'],
            }

    @classmethod
    def _get_from_shopify(cls, sale, transaction):
        assert (
            transaction['kind'] in {'AUTHORIZATION', 'SALE'}
            or (transaction['kind'] == 'REFUND'
                and not transaction['parentTransaction']))
        payment = cls(shopify_identifier=gid2id(transaction['id']))
        payment.company = sale.company
        payment.journal = sale.web_shop.get_payment_journal(
            transaction['amountSet']['presentmentMoney']['currencyCode'],
            cls._get_shopify_payment_journal_pattern(
                sale, transaction))
        if transaction['kind'] == 'REFUND':
            payment.kind = 'payable'
        else:
            payment.kind = 'receivable'
        payment.amount = Decimal(
            transaction['amountSet']['presentmentMoney']['amount'])
        payment.origin = sale
        payment.party = sale.party
        return payment

    @classmethod
    def get_from_shopify(cls, sale, order):
        id2payments = {}
        to_process = defaultdict(list)
        transactions = [
            t for t in order['transactions'] if t['status'] == 'SUCCESS']
        # Order transactions to process parent first
        kinds = ['AUTHORIZATION', 'CAPTURE', 'SALE', 'VOID', 'REFUND']
        transactions.sort(key=lambda t: kinds.index(t['kind']))
        amounts = defaultdict(Decimal)
        for transaction in transactions:
            if (transaction['kind'] not in {'AUTHORIZATION', 'SALE'}
                    and not (transaction['kind'] == 'REFUND'
                        and not transaction['parentTransaction'])):
                continue
            payments = cls.search([
                    ('shopify_identifier', '=', gid2id(transaction['id'])),
                    ])
            if payments:
                payment, = payments
            else:
                payment = cls._get_from_shopify(sale, transaction)
                to_process[payment.company, payment.journal].append(payment)
            id2payments[gid2id(transaction['id'])] = payment
            amounts[gid2id(transaction['id'])] = Decimal(
                transaction['amountSet']['presentmentMoney']['amount'])
        cls.save(list(id2payments.values()))

        for (company, journal), payments in to_process.items():
            cls.submit(payments)
            cls.process(payments)

        captured = defaultdict(Decimal)
        voided = defaultdict(Decimal)
        refunded = defaultdict(Decimal)
        for transaction in transactions:
            if transaction['kind'] == 'SALE':
                payment = id2payments[gid2id(transaction['id'])]
                captured[payment] += Decimal(
                    transaction['amountSet']['presentmentMoney']['amount'])
            elif transaction['kind'] == 'CAPTURE':
                payment = id2payments[
                    gid2id(transaction['parentTransaction']['id'])]
                id2payments[gid2id(transaction['id'])] = payment
                captured[payment] += Decimal(
                    transaction['amountSet']['presentmentMoney']['amount'])
            elif transaction['kind'] == 'VOID':
                payment = id2payments[
                    gid2id(transaction['parentTransaction']['id'])]
                voided[payment] += Decimal(
                    transaction['amountSet']['presentmentMoney']['amount'])
            elif transaction['kind'] == 'REFUND':
                if not transaction['parentTransaction']:
                    payment = id2payments[gid2id(transaction['id'])]
                else:
                    payment = id2payments[
                        gid2id(transaction['parentTransaction']['id'])]
                    captured[payment] -= Decimal(
                        transaction['amountSet']['presentmentMoney']['amount'])
                refunded[payment] += Decimal(
                    transaction['amountSet']['presentmentMoney']['amount'])

        to_save = []
        for payment in id2payments.values():
            if payment.kind == 'payable':
                amount = refunded[payment]
            else:
                amount = captured[payment]
            if payment.amount != amount:
                payment.amount = captured[payment]
                to_save.append(payment)
        cls.proceed(to_save)
        cls.save(to_save)

        to_succeed, to_fail, to_proceed = set(), set(), set()
        for transaction_id, payment in id2payments.items():
            amount = captured[payment] + voided[payment] + refunded[payment]
            if amounts[transaction_id] == amount:
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
