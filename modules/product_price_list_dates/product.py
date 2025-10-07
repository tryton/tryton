# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

import trytond.config as config
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Date, Eval, If, PYSONDecoder, PYSONEncoder
from trytond.transaction import Transaction


class PriceList(metaclass=PoolMeta):
    __name__ = 'product.price_list'

    @classmethod
    @ModelView.button_action(
        'product_price_list.act_price_list_line_form')
    def open_lines(cls, price_lists):
        encoder = PYSONEncoder()
        decoder = PYSONDecoder(noeval=True)
        action = super().open_lines(price_lists)
        context_domain = [
            ['OR',
                ('start_date', '=', None),
                ('start_date', '<=', Eval('date', Date())),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', Eval('date', Date())),
                ],
            ]
        if isinstance(action, dict):
            if action.get('context_domain'):
                context_domain = [
                    decoder.decode(action['context_domain']),
                    context_domain]
            action['context_domain'] = encoder.encode(context_domain)
        else:
            action = {
                'context_domain': encoder.encode(context_domain),
                }
        return action

    def compute(self, product, quantity, uom, pattern=None):
        context = Transaction().context
        pattern = pattern.copy() if pattern is not None else {}
        pattern.setdefault('date', context.get('date'))
        return super().compute(product, quantity, uom, pattern=pattern)


class PriceListCache(metaclass=PoolMeta):
    __name__ = 'product.price_list.cache'

    @classmethod
    def patterns(cls, price_list, product):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        for pattern in super().patterns(price_list, product):
            if pattern is None:
                pattern = {}
            for days in range(config.getint(
                        'product_price_list_dates', 'cache_days', default=2)):
                pattern['date'] = today + dt.timedelta(days=days)
                yield pattern

    @classmethod
    def get(cls, price_list, product, pattern=None):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        today = Date.today()
        pattern = pattern.copy() if pattern else {}
        pattern['date'] = pattern.get('date', context.get('date')) or today
        return super().get(price_list, product, pattern=pattern)


class PriceListLine(metaclass=PoolMeta):
    __name__ = 'product.price_list.line'

    start_date = fields.Date(
        "Start Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('start_date', '<=', Eval('end_date')),
                ()),
            ])
    end_date = fields.Date(
        "End Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('end_date', '>=', Eval('start_date')),
                ()),
            ])

    def match(self, pattern):
        pool = Pool()
        Date = pool.get('ir.date')

        pattern = pattern.copy()
        date = pattern.pop('date', None) or Date.today()
        if self.start_date and self.start_date > date:
            return False
        if self.end_date and self.end_date < date:
            return False
        return super().match(pattern)


class PriceListLineContext(metaclass=PoolMeta):
    __name__ = 'product.price_list.line.context'

    date = fields.Date("Date")

    @classmethod
    def default_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()


class SaleContext(metaclass=PoolMeta):
    __name__ = 'product.sale.context'

    date = fields.Function(
        fields.Date("Date"),
        'on_change_with_date')

    @fields.depends('sale_date')
    def on_change_with_date(self, name=None):
        return self.sale_date
