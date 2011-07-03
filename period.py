#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
from itertools import chain
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Equal, Eval, If, In, Get
from trytond.transaction import Transaction
from trytond.pool import Pool


class Period(ModelSQL, ModelView):
    'Stock Period'
    _name = 'stock.period'
    _description = __doc__
    _rec_name = 'date'
    date = fields.Date('Date', required=True, states={
        'readonly': Equal(Eval('state'), 'closed'),
        })
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Get(Eval('context', {}), 'company', 0)),
        ])
    caches = fields.One2Many('stock.period.cache', 'period', 'Caches')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('closed', 'Closed'),
        ], 'State', select=1, readonly=True)

    def __init__(self):
        super(Period, self).__init__()
        self._rpc.update({
            'button_draft': True,
            'button_close': True,
        })
        self._error_messages.update({
            'close_period_future_today': ('You can not close a period '
                'in the future or today!'),
            'close_period_assigned_move': ('You can not close a period when '
                'there is still assigned moves!'),
        })

    def button_draft(self, ids):
        cache_obj = Pool().get('stock.period.cache')
        cache_ids = []
        for i in xrange(0, len(ids), Transaction().cursor.IN_MAX):
            cache_ids.append(cache_obj.search([
                ('period', 'in', ids[i:i + Transaction().cursor.IN_MAX]),
            ], order=[]))
        cache_obj.delete(list(chain(*cache_ids)))
        self.write(ids, {
            'state': 'draft',
        })
        return True

    def button_close(self, ids):
        pool = Pool()
        product_obj = pool.get('product.product')
        location_obj = pool.get('stock.location')
        cache_obj = pool.get('stock.period.cache')
        move_obj = pool.get('stock.move')
        date_obj = pool.get('ir.date')

        location_ids = location_obj.search([
            ('type', 'not in', ['warehouse', 'view']),
        ], order=[])
        today = date_obj.today()
        periods = self.browse(ids)

        recent_date = max(period.date for period in periods)
        if recent_date >= today:
            self.raise_user_error('close_period_future_today')
        if move_obj.search([
                ('state', '=', 'assigned'),
                ['OR', [
                    ('effective_date', '=', False),
                    ('planned_date', '<=', recent_date),
                ],
                    ('effective_date', '<=', recent_date),
                ]]):
            self.raise_user_error('close_period_assigned_move')

        for period in periods:
            with Transaction().set_context(
                stock_date_end=period.date,
                stock_date_start=None,
                stock_assign=False,
                forecast=False,
                stock_destinations=None,
            ):
                pbl = product_obj.products_by_location(location_ids)
            for (location_id, product_id), quantity in pbl.iteritems():
                cache_obj.create({
                    'period': period.id,
                    'location': location_id,
                    'product': product_id,
                    'internal_quantity': quantity,
                })
        self.write(ids, {
            'state': 'closed',
        })
        return True

Period()


class Cache(ModelSQL, ModelView):
    '''
    Stock Period Cache

    It is used to store cached computation of stock quantities.
    '''
    _name = 'stock.period.cache'
    _description = __doc__

    period = fields.Many2One('stock.period', 'Period', required=True,
        readonly=True, select=1, ondelete='CASCADE')
    location = fields.Many2One('stock.location', 'Location', required=True,
        readonly=True, select=1, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product', required=True,
        readonly=True, select=1, ondelete='CASCADE')
    internal_quantity = fields.Float('Internal Quantity', readonly=True)

Cache()
