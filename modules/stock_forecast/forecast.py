#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelWorkflow, ModelSQL, fields
from trytond.wizard import Wizard
import datetime
import mx.DateTime

STATES = {
    'readonly': "state != 'draft'",
}


class Forecast(ModelWorkflow, ModelSQL, ModelView):
    "Stock Forecast"
    _name = "stock.forecast"
    _description = __doc__
    _rec_name = 'location'

    location = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'storage')], states={
            'readonly': "state != 'draft' or bool(lines)",
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
            'readonly': "state != 'draft' or bool(lines)",
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

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_destination(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.destination.domain, context=context)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

    def check_date_overlap(self, cursor, user, ids):
        for forecast in self.browse(cursor, user, ids):
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

    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)
        return True

    def set_state_draft(self, cursor, user, forecast_id, context=None):
        line_obj = self.pool.get("stock.forecast.line")
        forecast = self.browse(cursor, user, forecast_id, context=context)
        if forecast.state == "done":
            line_obj.cancel_moves(cursor, user, forecast.lines, context=context)
        self.write(cursor, user, forecast_id, {
            'state': 'draft',
            }, context=context)

    def set_state_cancel(self, cursor, user, forecast_id, context=None):
        self.write(cursor, user, forecast_id, {
            'state': 'cancel',
            }, context=context)

    def set_state_done(self, cursor, user, forecast_id, context=None):
        line_obj = self.pool.get('stock.forecast.line')
        forecast = self.browse(cursor, user, forecast_id, context=context)

        for line in forecast.lines:
            line_obj.create_moves(cursor, user, line, context=context)
        self.write(
            cursor, user, forecast_id, {'state': 'done',}, context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
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
        for forecast in self.browse(cursor, user, ids, context=context):
            new_id = super(Forecast, self).copy(cursor, user, forecast.id,
                    default=default, context=context)
            line_obj.copy(cursor, user, [x.id for x in forecast.lines],
                    default={
                        'forecast': new_id,
                    }, context=context)
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
        domain="[('category', '=', (product, 'product.default_uom.category'))]",
        on_change=['uom'])
    unit_digits = fields.Function('get_unit_digits', type='integer',
            string='Unit Digits')
    quantity = fields.Float('Quantity', digits="(16, unit_digits)", required=True)
    minimal_quantity = fields.Float(
        'Minimal Qty', digits="(16, unit_digits)", required=True)
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

    def default_unit_digits(self, cursor, user, context=None):
        return 2

    def default_minimal_quantity(self, cursor, user, context=None):
        return 1.0

    def on_change_product(self, cursor, user, ids, vals, context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        res = {}
        res['unit_digits'] = 2
        if vals.get('product'):
            product = product_obj.browse(cursor, user, vals['product'],
                    context=context)
            res['uom'] = product.default_uom.id
            res['uom.rec_name'] = product.default_uom.rec_name
            res['unit_digits'] = product.default_uom.digits
        return res

    def on_change_uom(self, cursor, user, ids, vals, context=None):
        uom_obj = self.pool.get('product.uom')
        res = {}
        res['unit_digits'] = 2
        if vals.get('uom'):
            uom = uom_obj.browse(cursor, user, vals['uom'], context=context)
            res['unit_digits'] = uom.digits
        return res

    def get_unit_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            res[line.id] = line.product.default_uom.digits
        return res

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = False
        return super(ForecastLine, self).copy(cursor, user, ids,
                default=default, context=context)

    def create_moves(self, cursor, user, line, context=None):
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        delta = line.forecast.to_date - line.forecast.from_date
        delta = delta.days + 1
        nb_packet = int(line.quantity/line.minimal_quantity)
        distribution = self.distribute(
            cursor, user, delta, nb_packet, context=context)
        unit_price = False
        if line.forecast.destination.type == 'customer':
            unit_price = line.product.list_price
            unit_price = uom_obj.compute_price(
                cursor, user, line.product.default_uom, unit_price, line.uom,
                context=context)

        moves = []
        for day, qty in distribution.iteritems():
            if qty == 0.0:
                continue
            mid = move_obj.create(
                cursor, user,
                {'from_location': line.forecast.location.id,
                 'to_location': line.forecast.destination.id,
                 'product': line.product.id,
                 'uom': line.uom.id,
                 'quantity': qty * line.minimal_quantity,
                 'planned_date': line.forecast.from_date + datetime.timedelta(day),
                 'company': line.forecast.company.id,
                 'currency':line.forecast.company.currency.id,
                 'unit_price': unit_price,
                 },
                context=context)
            moves.append(('add',mid))
        self.write(cursor, user, line.id, {'moves': moves}, context=context)

    def cancel_moves(self, cursor, user, lines, context=None):
        move_obj = self.pool.get('stock.move')
        move_obj.write(
            cursor, user, [m.id for l in lines for m in l.moves], {'state': 'cancel'},
            context=context)
        move_obj.delete(
            cursor, user, [m.id for l in lines for m in l.moves], context=context)

    def distribute(self, cursor, user, delta, qty, context=None):
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


    def _set_default_dates(self, cursor, user, data, context=None):
        """
        Forecast dates shifted by one year.
        """
        forecast_obj = self.pool.get('stock.forecast')
        forecast = forecast_obj.browse(cursor, user, data['id'], context=context)

        res = {}
        for field in ("to_date", "from_date"):
            date = mx.DateTime.strptime(str(forecast[field]), '%Y-%m-%d')
            new_date = date - mx.DateTime.RelativeDateTime(years=1)
            res[field] = datetime.date(new_date.year, new_date.month,
                    new_date.day)
        return res

    def _get_product_quantity(self, cursor, user, data, context=None):
        forecast_obj = self.pool.get('stock.forecast')
        product_obj = self.pool.get('product.product')
        forecast = forecast_obj.browse(cursor, user, data['id'], context=context)
        if data['form']['from_date'] > data['form']['to_date']:
            self.raise_user_error(cursor, 'from_to_date', context=context)
        local_context = context and context.copy() or {}
        local_context['stock_destinations'] = [forecast.destination.id]
        local_context['stock_date_start'] = data['form']['from_date']
        local_context['stock_date_end'] = data['form']['to_date']

        return product_obj.products_by_location(
            cursor, user, [forecast.location.id], with_childs=True,
            skip_zero=False, context=local_context)

    def _set_default_products(self, cursor, user, data, context=None):
        """
        Collect products for which there is an outgoing stream between
        the given location and the destination.
        """
        pbl = self._get_product_quantity(cursor, user, data, context=context)
        products = []
        for (_, product), qty in pbl.iteritems():
            if qty < 0:
                products.append(product)
        data['form'].update({'products': products})
        return data['form']

    def _complete(self, cursor, user, data, context=None):
        forecast_obj = self.pool.get('stock.forecast')
        forecast_line_obj = self.pool.get('stock.forecast.line')
        product_obj = self.pool.get('product.product')

        prod2line = {}
        forecast_line_ids = forecast_line_obj.search(
            cursor, user, [('forecast', '=', data['id'])], context=context)
        for forecast_line in forecast_line_obj.browse(
            cursor, user, forecast_line_ids, context=context):
            prod2line[forecast_line.product.id] = forecast_line.id

        pbl = self._get_product_quantity(cursor, user, data, context=context)
        product_ids = [x[1] for x in pbl]
        prod2uom = {}
        for product in product_obj.browse(cursor, user, product_ids,
                                          context=context):
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
                forecast_line_obj.write(
                    cursor, user, prod2line[product],
                    {'product': product,
                     'quantity': -qty,
                     'uom': prod2uom[product],
                     'forecast': data['id'],
                     'minimal_quantity': min(1, -qty),
                     },
                    context=context)
            else:
                forecast_line_obj.create(
                    cursor, user,
                    {'product': product,
                     'quantity': -qty,
                     'uom': prod2uom[product],
                     'forecast': data['id'],
                     'minimal_quantity': min(1, -qty),
                     },
                    context=context)
        return {}

ForecastComplete()
