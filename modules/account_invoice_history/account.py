# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.functions import CurrentTimestamp

from trytond.model import ModelView, Workflow, fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    numbered_at = fields.Timestamp("Numbered At")

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
        cls._check_modify_exclude.append('numbered_at')
        cls.party.datetime_field = 'numbered_at'
        if 'numbered_at' not in cls.party.depends:
            cls.party.depends.append('numbered_at')
        cls.invoice_address.datetime_field = 'numbered_at'
        if 'numbered_at' not in cls.invoice_address.depends:
            cls.invoice_address.depends.append('numbered_at')
        cls.payment_term.datetime_field = 'numbered_at'
        if 'numbered_at' not in cls.payment_term.depends:
            cls.payment_term.depends.append('numbered_at')

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
