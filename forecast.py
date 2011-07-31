#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import datetime
import time
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, ModelWorkflow, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.pyson import Not, Equal, Eval, Or, Bool
from trytond.backend import TableHandler
from trytond.transaction import Transaction

STATES = {
    'readonly': Not(Equal(Eval('state'), 'draft')),
}


class Forecast(ModelWorkflow, ModelSQL, ModelView):
    "Stock Forecast"
    _name = "stock.forecast"
    _description = __doc__
    _rec_name = 'location'

    location = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'storage')], states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines'))),
        })
    destination = fields.Many2One(
        'stock.location', 'Destination', required=True,
        domain=[('type', '=', 'customer')], states=STATES)
    from_date = fields.Date('From Date', required=True, states=STATES)
    to_date = fields.Date('To Date', required=True, states=STATES)
    lines = fields.One2Many(
        'stock.forecast.line', 'forecast', 'Lines', states=STATES)
    company = fields.Many2One(
        'company.company', 'Company', required=True, states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines'))),
        })
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], 'State', readonly=True, select=1)

    def __init__(self):
        super(Forecast, self).__init__()
        self._rpc.update({
            'button_draft': True,
        })
        self._sql_constraints += [
            ('check_from_to_date',
             'CHECK(to_date >= from_date)',
             '"To Date" must be greater than "From Date"!'),
            ]
        self._constraints += [
            ('check_date_overlap', 'date_overlap'),
            ]
        self._error_messages.update({
                'date_overlap': 'You can not create forecasts for the same '
                'locations with overlapping dates'
                })
        self._order.insert(0, ('from_date', 'DESC'))
        self._order.insert(1, ('location', 'ASC'))

    def init(self, module_name):
        cursor = Transaction().cursor
        super(Forecast, self).init(module_name)

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

    def default_state(self):
        return 'draft'

    def default_destination(self):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(
                self.destination.domain)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

    def check_date_overlap(self, ids):
        cursor = Transaction().cursor
        for forecast in self.browse(ids):
            if forecast.state != 'done':
                continue
            cursor.execute('SELECT id ' \
                    'FROM stock_forecast ' \
                    'WHERE ((from_date <= %s AND to_date >= %s) ' \
                            'OR (from_date <= %s AND to_date >= %s) ' \
                            'OR (from_date >= %s AND to_date <= %s)) ' \
                        'AND location = %s ' \
                        'AND destination = %s ' \
                        'AND state = \'done\' ' \
                        'AND company = %s '
                        'AND id != %s',
                    (forecast.from_date, forecast.from_date,
                     forecast.to_date, forecast.to_date,
                     forecast.from_date, forecast.to_date,
                     forecast.location.id, forecast.destination.id,
                     forecast.company.id, forecast.id))
            rowcount = cursor.rowcount
            if rowcount == -1 or rowcount is None:
                rowcount = len(cursor.fetchall())
            if rowcount:
                return False
        return True

    def button_draft(self, ids):
        self.workflow_trigger_create(ids)
        return True

    def set_state_draft(self, forecast_id):
        line_obj = self.pool.get("stock.forecast.line")
        forecast = self.browse(forecast_id)
        if forecast.state == "done":
            line_obj.cancel_moves(forecast.lines)
        self.write(forecast_id, {
            'state': 'draft',
            })

    def set_state_cancel(self, forecast_id):
        self.write(forecast_id, {
            'state': 'cancel',
            })

    def set_state_done(self, forecast_id):
        line_obj = self.pool.get('stock.forecast.line')
        forecast = self.browse(forecast_id)

        for line in forecast.lines:
            line_obj.create_moves(line)
        self.write(forecast_id, {
            'state': 'done',
            })

    def copy(self, ids, default=None):
        line_obj = self.pool.get('stock.forecast.line')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if default is None:
            default = {}
        default = default.copy()
        default['lines'] = False

        new_ids = []
        for forecast in self.browse(ids):
            new_id = super(Forecast, self).copy(forecast.id, default=default)
            line_obj.copy([x.id for x in forecast.lines],
                    default={
                        'forecast': new_id,
                    })
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

Forecast()


class ForecastLine(ModelSQL, ModelView):
    'Stock Forecast Line'
    _name = 'stock.forecast.line'
    _description = __doc__
    _rec_name = 'product'

    product = fields.Many2One('product.product', 'Product', required=True,
            domain=[('type', '=', 'stockable')], on_change=['product'])
    uom = fields.Many2One(
        'product.uom', 'UOM', required=True,
        domain=[
            ('category', '=',
                (Eval('product'), 'product.default_uom.category')),
        ], on_change=['uom'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
            'get_unit_digits')
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
            required=True)
    minimal_quantity = fields.Float('Minimal Qty',
            digits=(16, Eval('unit_digits', 2)), required=True)
    moves = fields.Many2Many('stock.forecast.line-stock.move',
            'line', 'move','Moves', readonly=True)
    forecast = fields.Many2One(
        'stock.forecast', 'Forecast', required=True, ondelete='CASCADE',)

    def __init__(self):
        super(ForecastLine, self).__init__()
        self._sql_constraints += [
            ('check_line_qty_pos',
             'CHECK(quantity >= 0.0)', 'Line quantity must be positive!'),
            ('check_line_minimal_qty',
             'CHECK(quantity >= minimal_quantity)',
             'Line quantity must be greater than the minimal quantity!'),
            ('forecast_product_uniq', 'UNIQUE(forecast, product)',
             'Product must be unique by forcast!'),
        ]

    def default_unit_digits(self):
        return 2

    def default_minimal_quantity(self):
        return 1.0

    def on_change_product(self, vals):
        product_obj = self.pool.get('product.product')
        res = {}
        res['unit_digits'] = 2
        if vals.get('product'):
            product = product_obj.browse(vals['product'])
            res['uom'] = product.default_uom.id
            res['uom.rec_name'] = product.default_uom.rec_name
            res['unit_digits'] = product.default_uom.digits
        return res

    def on_change_uom(self, vals):
        uom_obj = self.pool.get('product.uom')
        res = {}
        res['unit_digits'] = 2
        if vals.get('uom'):
            uom = uom_obj.browse(vals['uom'])
            res['unit_digits'] = uom.digits
        return res

    def get_unit_digits(self, ids, name):
        res = {}
        for line in self.browse(ids):
            res[line.id] = line.product.default_uom.digits
        return res

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = False
        return super(ForecastLine, self).copy(ids, default=default)

    def create_moves(self, line):
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        delta = line.forecast.to_date - line.forecast.from_date
        delta = delta.days + 1
        nb_packet = int(line.quantity/line.minimal_quantity)
        distribution = self.distribute(delta, nb_packet)
        unit_price = False
        if line.forecast.destination.type == 'customer':
            unit_price = line.product.list_price
            unit_price = uom_obj.compute_price(line.product.default_uom, 
                    unit_price, line.uom)

        moves = []
        for day, qty in distribution.iteritems():
            if qty == 0.0:
                continue
            mid = move_obj.create({
                'from_location': line.forecast.location.id,
                'to_location': line.forecast.destination.id,
                'product': line.product.id,
                'uom': line.uom.id,
                'quantity': qty * line.minimal_quantity,
                'planned_date': line.forecast.from_date + datetime.timedelta(day),
                'company': line.forecast.company.id,
                'currency':line.forecast.company.currency.id,
                'unit_price': unit_price,
                })
            moves.append(('add',mid))
        self.write(line.id, {'moves': moves})

    def cancel_moves(self, lines):
        move_obj = self.pool.get('stock.move')
        move_obj.write([m.id for l in lines for m in l.moves], 
                {'state': 'cancel'})
        move_obj.delete([m.id for l in lines for m in l.moves])

    def distribute(self, delta, qty):
        range_delta = range(delta)
        a = {}.fromkeys(range_delta, 0)
        while qty > 0:
            if qty > delta:
                for i in range_delta:
                    a[i] += qty//delta
                qty = qty%delta
            elif delta//qty > 1:
                i = 0
                while i < qty:
                    a[i*delta//qty + (delta//qty/2)] += 1
                    i += 1
                qty = 0
            else:
                for i in range_delta:
                    a[i] += 1
                qty = delta-qty
                i = 0
                while i < qty:
                    a[delta - ((i*delta//qty) + (delta//qty/2)) - 1] -= 1
                    i += 1
                qty = 0
        return a

ForecastLine()


class ForecastLineMove(ModelSQL):
    'ForecastLine - Move'
    _name = 'stock.forecast.line-stock.move'
    _table = 'forecast_line_stock_move_rel'
    _description = __doc__
    line = fields.Many2One('stock.forecast.line', 'Forecast Line',
            ondelete='CASCADE', select=1, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='CASCADE',
            select=1, required=True)

ForecastLineMove()


class ForecastCompleteAsk(ModelView):
    'Forecast Complete Ask'
    _name = 'stock.forecast.complete.ask'
    _description = __doc__
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)

ForecastCompleteAsk()


class ForecastCompleteChoose(ModelView):
    'Forecast Complete Choose'
    _name = 'stock.forecast.complete.choose'
    _description = __doc__
    products = fields.Many2Many('product.product', None, None, 'Products')

ForecastCompleteChoose()


class ForecastComplete(Wizard):
    'Complete Forecast'
    _name = 'stock.forecast.complete'
    states = {
        'init': {
            'actions': ['_set_default_dates'],
            'result': {
                'type': 'form',
                'object': 'stock.forecast.complete.ask',
                'state': [
                    ('end', 'cancel', 'tryton-cancel'),
                    ('choose', 'Choose products', 'tryton-go-next'),
                    ('complete', 'Complete', 'tryton-ok', True),
                ],
            },
        },

        'choose': {
            'actions': ['_set_default_products'],
            'result': {
                'type': 'form',
                'object': 'stock.forecast.complete.choose',
                'state': [
                    ('end', 'cancel', 'tryton-cancel'),
                    ('init', 'Choose Dates', 'tryton-go-previous'),
                    ('complete', 'Complete', 'tryton-ok', True),
                ],
            },
        },

        'complete': {
            'result': {
                'type': 'action',
                'action': '_complete',
                'state': 'end',
                },
            },
        }

    def __init__(self):
        super(ForecastComplete, self).__init__()
        self._error_messages.update({
            'from_to_date': '"From Date" should be smaller than "To Date"!',
            })


    def _set_default_dates(self, data):
        """
        Forecast dates shifted by one year.
        """
        forecast_obj = self.pool.get('stock.forecast')
        forecast = forecast_obj.browse(data['id'])

        res = {}
        for field in ("to_date", "from_date"):
            res[field] = forecast[field] - relativedelta(years=1)
        return res

    def _get_product_quantity(self, data):
        forecast_obj = self.pool.get('stock.forecast')
        product_obj = self.pool.get('product.product')
        forecast = forecast_obj.browse(data['id'])
        if data['form']['from_date'] > data['form']['to_date']:
            self.raise_user_error('from_to_date')

        with Transaction().set_context(
                stock_destination=[forecast.destination.id],
                stock_date_start=data['form']['from_date'],
                stock_date_end=data['form']['to_date']):
            return product_obj.products_by_location([forecast.location.id], 
                    with_childs=True, skip_zero=False)

    def _set_default_products(self, data):
        """
        Collect products for which there is an outgoing stream between
        the given location and the destination.
        """
        pbl = self._get_product_quantity(data)
        products = []
        for (_, product), qty in pbl.iteritems():
            if qty < 0:
                products.append(product)
        data['form'].update({'products': products})
        return data['form']

    def _complete(self, data):
        forecast_obj = self.pool.get('stock.forecast')
        forecast_line_obj = self.pool.get('stock.forecast.line')
        product_obj = self.pool.get('product.product')

        prod2line = {}
        forecast_line_ids = forecast_line_obj.search([
            ('forecast', '=', data['id']),
            ])
        for forecast_line in forecast_line_obj.browse(forecast_line_ids):
            prod2line[forecast_line.product.id] = forecast_line.id

        pbl = self._get_product_quantity(data)
        product_ids = [x[1] for x in pbl]
        prod2uom = {}
        for product in product_obj.browse(product_ids):
            prod2uom[product.id] = product.default_uom.id

        if data['form'].get('products'):
            products = data['form']['products'][0][1]
        else:
            products = None

        for (_, product), qty in pbl.iteritems():
            if products and product not in products:
                continue
            if -qty <= 0:
                continue
            if product in prod2line:
                forecast_line_obj.write(prod2line[product],{
                    'product': product,
                    'quantity': -qty,
                    'uom': prod2uom[product],
                    'forecast': data['id'],
                    'minimal_quantity': min(1, -qty),
                    })
            else:
                forecast_line_obj.create({
                    'product': product,
                    'quantity': -qty,
                    'uom': prod2uom[product],
                    'forecast': data['id'],
                    'minimal_quantity': min(1, -qty),
                    })
        return {}

ForecastComplete()
