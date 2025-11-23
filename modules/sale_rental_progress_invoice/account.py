# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.report import Report
from trytond.tools import cached_property


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    def get_sale_rentals(self, name):
        pool = Pool()
        RentalProgress = pool.get('sale.rental.progress')
        rentals = set(super().get_sale_rentals(name))
        for line in self.lines:
            if isinstance(line.origin, RentalProgress):
                rentals.add(line.origin.rental.id)
        return list(rentals)

    @classmethod
    def search_sale_rentals(cls, name, clause):
        domain = super().search_sale_rentals(name, clause)
        operator = clause[1]
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            domain,
            ('lines.origin.rental' + clause[0][len(name):],
                *clause[1:3], 'sale.rental.progress', *clause[3:]),
            ]


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('product', 'origin')
    def on_change_product(self):
        pool = Pool()
        RentalProgress = pool.get('sale.rental.progress')
        super().on_change_product()
        if self.product and isinstance(self.origin, RentalProgress):
            # Prevent warning from Invoice._check_taxes
            if self.origin.lines:
                self.taxes = self.origin.lines[0].taxes
            else:
                self.taxes = []

    @cached_property
    def product_name(self):
        pool = Pool()
        RentalLine = pool.get('sale.rental.line')
        RentalProgress = pool.get('sale.rental.progress')
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        name = super().product_name
        if isinstance(self.origin, RentalProgress):
            converter = RentalLine.duration.converter
            duration = Report.format_timedelta(
                self.origin.duration, converter=converter, lang=lang)
            start = lang.strftime(self.origin.start)
            end = lang.strftime(self.origin.end)
            name = f'[{start} -- {end}] {duration} × {name}'
        return name

    @property
    def origin_name(self):
        pool = Pool()
        RentalProgress = pool.get('sale.rental.progress')
        name = super().origin_name
        if isinstance(self.origin, RentalProgress):
            name = self.origin.rental.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        models = super()._get_origin()
        models.append('sale.rental.progress')
        return models


class InvoiceLine_Asset(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('origin')
    def on_change_with_is_assets_depreciable(self, name=None):
        pool = Pool()
        RentalProgress = pool.get('sale.rental.progress')
        depreciable = super().on_change_with_is_assets_depreciable(name=name)
        if depreciable and isinstance(self.origin, RentalProgress):
            depreciable = False
        return depreciable
