# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.conditionals import Greatest
from sql.functions import CurrentTimestamp

from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    numbered_at = fields.Timestamp("Numbered At")
    history_datetime = fields.Function(
        fields.Timestamp("History DateTime"),
        'get_history_datetime')

    @classmethod
    def __register__(cls, module_name):
        super().__register__(module_name)
        table_h = cls.__table_handler__(module_name)
        table = cls.__table__()
        cursor = Transaction().connection.cursor()

        # Migration from 5.2: rename open_date into numbered_at
        if table_h.column_exist('open_date'):
            cursor.execute(
                *table.update(
                    [table.numbered_at],
                    [table.open_date]))
            table_h.drop_column('open_date')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._check_modify_exclude.add('numbered_at')
        cls.party.datetime_field = 'history_datetime'
        cls.invoice_address.datetime_field = 'history_datetime'
        cls.payment_term.datetime_field = 'history_datetime'

    @classmethod
    def get_history_datetime(cls, invoices, name):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        PaymentTerm = pool.get('account.invoice.payment_term')
        table = cls.__table__()
        party = Party.__table__()
        address = Address.__table__()
        payment_term = PaymentTerm.__table__()
        cursor = Transaction().connection.cursor()

        invoice_ids = [i.id for i in invoices]
        datetimes = dict.fromkeys(invoice_ids)
        for ids in grouped_slice(invoice_ids):
            cursor.execute(*table
                .join(party, condition=table.party == party.id)
                .join(address, condition=table.invoice_address == address.id)
                .join(payment_term, 'LEFT',
                    condition=table.payment_term == payment_term.id)
                .select(table.id,
                    Greatest(table.numbered_at, party.create_date,
                        address.create_date, payment_term.create_date),
                    where=reduce_ids(table.id, ids)
                    & (table.numbered_at != Null)))
            datetimes.update(cursor)
        return datetimes

    @classmethod
    def set_number(cls, invoices):
        numbered = [i for i in invoices if not i.number or not i.numbered_at]
        super(Invoice, cls).set_number(invoices)
        if numbered:
            cls.write(numbered, {
                    'numbered_at': CurrentTimestamp(),
                    })

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, invoices):
        super(Invoice, cls).draft(invoices)
        cls.write(invoices, {
                'numbered_at': None,
                })

    @classmethod
    def copy(cls, invoices, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('numbered_at', None)
        return super(Invoice, cls).copy(invoices, default=default)
