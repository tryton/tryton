#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import chain
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Equal, Eval, If, In, Get
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Period', 'Cache']


class Period(ModelSQL, ModelView):
    'Stock Period'
    __name__ = 'stock.period'
    _rec_name = 'date'
    date = fields.Date('Date', required=True, states={
        'readonly': Equal(Eval('state'), 'closed'),
        }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ])
    caches = fields.One2Many('stock.period.cache', 'period', 'Caches')
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
                'close_period_assigned_move': ('You can not close a period when '
                    'there still are assigned moves.'),
                })
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    },
                'close': {
                    'invisible': Eval('state') == 'closed',
                    },
                })

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    @ModelView.button
    def draft(cls, periods):
        Cache = Pool().get('stock.period.cache')
        caches = []
        for i in xrange(0, len(periods), Transaction().cursor.IN_MAX):
            caches.append(Cache.search([
                ('period', 'in', [p.id for p in
                                periods[i:i + Transaction().cursor.IN_MAX]]),
                        ], order=[]))
        Cache.delete(list(chain(*caches)))
        cls.write(periods, {
                'state': 'draft',
                })

    @classmethod
    @ModelView.button
    def close(cls, periods):
        pool = Pool()
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Cache = pool.get('stock.period.cache')
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

        to_create = []
        for period in periods:
            with Transaction().set_context(
                    stock_date_end=period.date,
                    stock_date_start=None,
                    stock_assign=False,
                    forecast=False,
                    stock_destinations=None,
                    ):
                pbl = Product.products_by_location([l.id for l in locations])
            for (location_id, product_id), quantity in pbl.iteritems():
                to_create.append({
                        'period': period.id,
                        'location': location_id,
                        'product': product_id,
                        'internal_quantity': quantity,
                        })
        if to_create:
            Cache.create(to_create)
        cls.write(periods, {
                'state': 'closed',
                })


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
