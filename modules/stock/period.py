# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import chain
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import grouped_slice

__all__ = ['Period', 'Cache']


class Period(Workflow, ModelSQL, ModelView):
    'Stock Period'
    __name__ = 'stock.period'
    _rec_name = 'date'
    date = fields.Date('Date', required=True, states={
            'readonly': Eval('state') == 'closed',
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    caches = fields.One2Many('stock.period.cache', 'period', 'Caches',
        readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('closed', 'Closed'),
        ], 'State', select=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super(Period, cls).__setup__()
        cls._error_messages.update({
                'close_period_future_today': ('You can not close a period '
                    'in the future or today.'),
                'close_period_assigned_move': (
                    'You can not close a period when '
                    'there still are assigned moves.'),
                })
        cls._transitions |= set((
                ('draft', 'closed'),
                ('closed', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    },
                'close': {
                    'invisible': Eval('state') == 'closed',
                    },
                })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def groupings():
        return [('product',)]

    @staticmethod
    def get_cache(grouping):
        pool = Pool()
        if grouping == ('product',):
            return pool.get('stock.period.cache')

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, periods):
        for grouping in cls.groupings():
            Cache = cls.get_cache(grouping)
            caches = []
            for sub_periods in grouped_slice(periods):
                caches.append(Cache.search([
                            ('period', 'in',
                                [p.id for p in sub_periods]),
                            ], order=[]))
            Cache.delete(list(chain(*caches)))

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, periods):
        pool = Pool()
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')

        locations = Location.search([
                ('type', 'not in', ['warehouse', 'view']),
                ], order=[])
        today = Date.today()

        recent_date = max(period.date for period in periods)
        if recent_date >= today:
            cls.raise_user_error('close_period_future_today')
        if Move.search([
                    ('state', '=', 'assigned'),
                    ['OR', [
                            ('effective_date', '=', None),
                            ('planned_date', '<=', recent_date),
                            ],
                        ('effective_date', '<=', recent_date),
                        ]]):
            cls.raise_user_error('close_period_assigned_move')

        for grouping in cls.groupings():
            Cache = cls.get_cache(grouping)
            to_create = []
            for period in periods:
                with Transaction().set_context(
                        stock_date_end=period.date,
                        stock_date_start=None,
                        stock_assign=False,
                        forecast=False,
                        stock_destinations=None,
                        ):
                    pbl = Product.products_by_location(
                        [l.id for l in locations], grouping=grouping)
                for key, quantity in pbl.iteritems():
                    values = {
                        'location': key[0],
                        'period': period.id,
                        'internal_quantity': quantity,
                        }
                    for i, field in enumerate(grouping, 1):
                        values[field] = key[i]
                    to_create.append(values)
            if to_create:
                Cache.create(to_create)


class Cache(ModelSQL, ModelView):
    '''
    Stock Period Cache

    It is used to store cached computation of stock quantities.
    '''
    __name__ = 'stock.period.cache'
    period = fields.Many2One('stock.period', 'Period', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    location = fields.Many2One('stock.location', 'Location', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    internal_quantity = fields.Float('Internal Quantity', readonly=True)
