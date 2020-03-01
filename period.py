# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import chain

from sql import Literal, For

from trytond.i18n import gettext
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import grouped_slice

from .exceptions import PeriodCloseError


class Period(Workflow, ModelSQL, ModelView):
    'Stock Period'
    __name__ = 'stock.period'
    date = fields.Date('Date', required=True, states={
            'readonly': Eval('state') == 'closed',
            }, depends=['state'],
        help="When the stock period ends.")
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        help="The company the stock period is associated with.")
    caches = fields.One2Many('stock.period.cache', 'period', 'Caches',
        readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('closed', 'Closed'),
        ], 'State', select=True, readonly=True,
        help="The current state of the stock period.")

    @classmethod
    def __setup__(cls):
        super(Period, cls).__setup__()
        cls._transitions |= set((
                ('draft', 'closed'),
                ('closed', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    'depends': ['state'],
                    },
                'close': {
                    'invisible': Eval('state') == 'closed',
                    'depends': ['state'],
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
        if all(g == 'product' or g.startswith('product.') for g in grouping):
            return pool.get('stock.period.cache')

    def get_rec_name(self, name):
        return str(self.date)

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
        transaction = Transaction()
        connection = transaction.connection
        database = transaction.database

        # XXX: A move in the period could be inserted before the lock
        # from a different transaction. It will not be taken in the pbl
        # computation but it is quite rare because only past periods are
        # closed.
        database.lock(connection, Move._table)
        if database.has_select_for():
            move = Move.__table__()
            query = move.select(Literal(1), for_=For('UPDATE', nowait=True))
            with connection.cursor() as cursor:
                cursor.execute(*query)

        locations = Location.search([
                ('type', 'not in', ['warehouse', 'view']),
                ], order=[])
        today = Date.today()

        recent_date = max(period.date for period in periods)
        if recent_date >= today:
            raise PeriodCloseError(
                gettext('stock.msg_period_close_date'))
        if Move.search([
                    ('state', '=', 'assigned'),
                    ['OR', [
                            ('effective_date', '=', None),
                            ('planned_date', '<=', recent_date),
                            ],
                        ('effective_date', '<=', recent_date),
                        ]]):
            raise PeriodCloseError(
                gettext('stock.msg_period_close_assigned_move'))

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
                for key, quantity in pbl.items():
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
