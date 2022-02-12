# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta

from trytond.model import (
    DeactivableMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pool import Pool, PoolMeta


class InvoiceTerm(DeactivableMixin, ModelSQL, ModelView):
    "Invoice Term"
    __name__ = 'sale.invoice.term'

    name = fields.Char(
        "Name", required=True, translate=True,
        help="The main identifier of the invoice term.")
    relative_deltas = fields.One2Many(
        'sale.invoice.term.relative_delta', 'term', "Deltas")

    def get_date(self, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today()
        for relative_delta in self.relative_deltas:
            date += relative_delta.get()
        return date


class InvoiceTermRelativeDelta(sequence_ordered(), ModelSQL, ModelView):
    "Invoice Term Delta"
    __name__ = 'sale.invoice.term.relative_delta'

    term = fields.Many2One(
        'sale.invoice.term', "Invoice Term", required=True, ondelete='CASCADE')
    day = fields.Integer('Day of Month',
        domain=['OR',
            ('day', '=', None),
            [('day', '>=', 1), ('day', '<=', 31)],
            ])
    month = fields.Many2One('ir.calendar.month', "Month")
    weekday = fields.Many2One('ir.calendar.day', "Day of Week")
    months = fields.Integer('Number of Months', required=True)
    weeks = fields.Integer('Number of Weeks', required=True)
    days = fields.Integer('Number of Days', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('term')

    @classmethod
    def default_months(cls):
        return 0

    @classmethod
    def default_weeks(cls):
        return 0

    @classmethod
    def default_days(cls):
        return 0

    def get(self):
        "Return the relativedelta"
        return relativedelta(
            day=self.day,
            month=int(self.month.index) if self.month else None,
            days=self.days,
            weeks=self.weeks,
            months=self.months,
            weekday=int(self.weekday.index) if self.weekday else None,
            )


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    sale_invoice_term = fields.MultiValue(fields.Many2One(
            'sale.invoice.term', "Sale Invoice Term"))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'sale_invoice_term':
            return pool.get('sale.configuration.sale_method')
        return super().multivalue_model(field)


class ConfigurationSaleMethod(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sale_method'

    sale_invoice_term = fields.Many2One(
        'sale.invoice.term', "Sale Invoice Term")


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    invoice_term = fields.Many2One(
        'sale.invoice.term', "Invoice Term", ondelete='RESTRICT')

    @classmethod
    def default_invoice_term(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        config = Configuration(1)
        return config.get_multivalue('sale_invoice_term', **pattern)

    @fields.depends('party', 'company')
    def on_change_party(self):
        super().on_change_party()
        self.invoice_term = self.default_invoice_term(
            company=self.company.id if self.company else None)
        if self.party:
            if self.party.sale_invoice_term:
                self.invoice_term = self.party.sale_invoice_term

    @property
    def _invoice_term_date(self):
        return

    def _get_invoice_sale(self):
        invoice = super()._get_invoice_sale()
        if self.invoice_term:
            invoice.invoice_date = self.invoice_term.get_date(
                date=self._invoice_term_date)
        return invoice

    @property
    def _invoice_grouping_fields(self):
        return super()._invoice_grouping_fields + ('invoice_date',)
