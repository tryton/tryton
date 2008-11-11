#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
import datetime
from trytond.netsvc import LocalService

STATES = {
    'readonly': "state != 'draft'",
}


class Forecast(OSV):
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
        self._rpc_allowed += [
            'button_draft',
        ]
        self._sql_constraints += [
            ('check_from_to_date',
             'CHECK(to_date >= from_date)',
             '"To Date" must be greater than "From Date"!')
            ]
        self._constraints += [
            ('check_date_overlap', 'date_overlap'),
            ]
        self._error_messages.update({
                'date_overlap': 'You can not create forecasts for the same '
                'product with overlaping dates'
                })
        self._order.insert(0, ('from_date', 'DESC'))
        self._order.insert(1, ('location', 'ASC'))

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_destination(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.destination._domain, context=context)
        if len(location_ids) == 1:
            return location_obj.name_get(cursor, user, location_ids,
                    context=context)[0]
        return False

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

    def check_date_overlap(self, cursor, user, ids):
        for forecast in self.browse(cursor, user, ids):
            if forecast.state != 'done':
                continue
            cursor.execute('SELECT f.id ' \
                    'FROM stock_forecast f ' \
                    'JOIN stock_forecast_line l on (f.id = l.forecast) '
                    'WHERE ((f.from_date <= %s AND f.to_date >= %s) ' \
                            'OR (f.from_date <= %s AND f.to_date >= %s) ' \
                            'OR (f.from_date >= %s AND f.to_date <= %s)) ' \
                        'AND l.product in (%s) ' \
                        'AND state = \'done\' ' \
                        'AND f.id != %s',
                    (forecast.from_date, forecast.from_date,
                     forecast.to_date, forecast.to_date,
                     forecast.from_date, forecast.to_date,
                     ",".join((str(l.product.id) for l in forecast.lines)),
                     forecast.id))
            if cursor.rowcount:
                return False
        return True

    def button_draft(self, cursor, user, ids, context=None):
        workflow_service = LocalService('workflow')
        for forecast in self.browse(cursor, user, ids, context=context):
            workflow_service.trg_create(user, self._name, forecast.id, cursor,
                    context=context)
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

    def copy(self, cursor, user, forecast_id, default=None, context=None):
        line_obj = self.pool.get('stock.forecast.line')
        default = default and default.copy() or {}
        default['lines'] = False
        new_id = super(Forecast, self).copy(
            cursor, user, forecast_id, default=default, context=context)
        forecast = self.browse(cursor, user, forecast_id, context=context)
        for line in forecast.lines:
            line_obj.copy(
                cursor, user, line.id, default={
                    'forecast': new_id,
                    'moves': False},
                context=context)
        return new_id
Forecast()

class ForecastLine(OSV):
    'Stock Forecast Line'
    _name = 'stock.forecast.line'
    _description = __doc__
    _rec_name = 'product'

    product = fields.Many2One('product.product', 'Product', required=True,
            domain=[('type', '=', 'stockable')], on_change=['product'])
    uom = fields.Function('get_uom', type='many2one', relation='product.uom',
            string='UOM', required=True)
    unit_digits = fields.Function('get_unit_digits', type='integer',
            string='Unit Digits')
    quantity = fields.Float('Quantity', digits="(16, unit_digits)", required=True)
    minimal_quantity = fields.Float(
        'Minimal Qty', digits="(16, unit_digits)", required=True)
    moves = fields.Many2Many(
        'stock.move', 'forecast_line_stock_move_rel', 'line', 'move','Moves',
        readonly=True, ondelete_target='CASCADE')
    forecast = fields.Many2One('stock.forecast', 'Forecast', required=True)

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
            res['uom'] = uom_obj.name_get(cursor, user, product.default_uom.id,
                    context=context)[0]
            res['unit_digits'] = product.default_uom.digits
        return res

    def get_uom(self, cursor, user, ids, name, arg, context=None):
        uom_obj = self.pool.get('product.uom')
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            res[line.id] = line.product.default_uom.id
        uom2name = {}
        for uom_id, name in uom_obj.name_get(cursor, user, res.values(),
                context=context):
            uom2name[uom_id] = (uom_id, name)
        for line_id in res:
            res[line_id] = uom2name[res[line_id]]
        return res

    def get_unit_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            res[line.id] = line.product.default_uom.digits
        return res

    def create_moves(self, cursor, user, line, context=None):
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        delta = line.forecast.to_date - line.forecast.from_date
        delta = delta.days + 1
        nb_packet = int(line.quantity/line.minimal_quantity)
        distribution = self.distribute(delta, nb_packet)
        unit_price = False
        if line.forecast.destination.type == 'customer':
            unit_price = line.product.list_price
        elif line.forecast.destination.type == 'supplier':
            unit_price = line.product.cost_price
        if unit_price:
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
                 'currency':line.forecast.company.currency,
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

    @staticmethod
    def distribute(delta, qty):
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
