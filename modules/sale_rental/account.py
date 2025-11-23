# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.report import Report
from trytond.tools import cached_property


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    sale_rentals = fields.Function(fields.Many2Many(
            'sale.rental', None, None, "Rentals"),
        'get_sale_rentals', searcher='search_sale_rentals')

    def get_sale_rentals(self, name):
        pool = Pool()
        RentalLine = pool.get('sale.rental.line')
        rentals = set()
        for line in self.lines:
            if isinstance(line.origin, RentalLine):
                rentals.add(line.origin.rental.id)
        return list(rentals)

    @classmethod
    def search_sale_rentals(cls, name, clause):
        return [
            ('lines.origin.rental' + clause[0][len(name):],
                *clause[1:3], 'sale.rental.line', *clause[3:]),
            ]


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('product', 'origin')
    def on_change_product(self):
        pool = Pool()
        RentalLine = pool.get('sale.rental.line')
        super().on_change_product()
        if self.product and isinstance(self.origin, RentalLine):
            # Prevent warning from Invoice._check_taxes
            self.taxes = self.origin.taxes

    @cached_property
    def product_name(self):
        pool = Pool()
        RentalLine = pool.get('sale.rental.line')
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        name = super().product_name
        if isinstance(self.origin, RentalLine):
            converter = RentalLine.duration.converter
            duration = Report.format_timedelta(
                self.origin.duration_invoice, converter=converter, lang=lang)
            start = lang.strftime(self.origin.start_invoice)
            end = lang.strftime(self.origin.end_invoice)
            name = f'[{start} -- {end}] {duration} × {name}'
        return name

    @property
    def origin_name(self):
        pool = Pool()
        RentalLine = pool.get('sale.rental.line')
        name = super().origin_name
        if isinstance(self.origin, RentalLine):
            name = self.origin.rental.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        models = super()._get_origin()
        models.append('sale.rental.line')
        return models


class InvoiceLine_Asset(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('origin')
    def on_change_with_is_assets_depreciable(self, name=None):
        pool = Pool()
        RentalLine = pool.get('sale.rental.line')
        depreciable = super().on_change_with_is_assets_depreciable(name=name)
        if depreciable and isinstance(self.origin, RentalLine):
            depreciable = False
        return depreciable
