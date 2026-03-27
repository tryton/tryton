# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Work(metaclass=PoolMeta):
    __name__ = 'project.work'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.origin.domain['sale.line'] = [
            ('sale.company', '=', Eval('company', -1)),
            ]

    @classmethod
    def _get_origins(cls):
        return super()._get_origins() + ['sale.line']

    @classmethod
    def on_modification(cls, mode, works, field_names=None):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        super().on_modification(mode, works, field_names=field_names)
        if not field_names or 'progress' in field_names:
            sales = {
                w.origin.sale for w in works if isinstance(w.origin, SaleLine)}
            Sale.__queue__.process(sales)


class Work_Invoice(metaclass=PoolMeta):
    __name__ = 'project.work'

    @fields.depends('origin')
    def on_change_with_invoice_method(self, name=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        method = super().on_change_with_invoice_method(name=name)
        if isinstance(self.origin, SaleLine):
            method = 'manual'
        return method
