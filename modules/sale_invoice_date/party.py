# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    sale_invoice_term = fields.MultiValue(fields.Many2One(
            'sale.invoice.term', "Sale Invoice Term",
            help="The default sale invoice term for the customer.\n"
            "Leave empty to use the default value from the configuration."))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'sale_invoice_term':
            return pool.get('party.party.sale_method')
        return super().multivalue_model(field)

    @classmethod
    def copy(cls, parties, default=None):
        context = Transaction().context
        default = default.copy() if default else {}
        if context.get('_check_access'):
            default_values = cls.default_get(
                ['sale_invoice_term'], with_rec_name=False)
            default.setdefault(
                'sale_invoice_term', default_values.get('sale_invoice_term'))
        return super().copy(parties, default=default)


class PartySaleMethod(metaclass=PoolMeta):
    __name__ = 'party.party.sale_method'

    sale_invoice_term = fields.Many2One(
        'sale.invoice.term', "Sale Invoice Term", ondelete='RESTRICT')
