#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from dateutil.relativedelta import relativedelta
import itertools
from trytond.model import ModelView, Workflow, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Not, Equal, Eval, Or, Bool, If
from trytond.backend import TableHandler
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import reduce_ids

STATES = {
    'readonly': Not(Equal(Eval('state'), 'draft')),
}
DEPENDS = ['state']


class Forecast(Workflow, ModelSQL, ModelView):
    "Stock Forecast"
    _name = "stock.forecast"
    _description = __doc__
    _rec_name = 'warehouse'

    warehouse = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'warehouse')], states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines'))),
            },
        depends=['state', 'lines'])
    destination = fields.Many2One(
        'stock.location', 'Destination', required=True,
        domain=[('type', 'in', ['customer', 'production'])], states=STATES,
        depends=DEPENDS)
    from_date = fields.Date('From Date', required=True, states=STATES,
        depends=DEPENDS)
    to_date = fields.Date('To Date', required=True, states=STATES,
        depends=DEPENDS)
    lines = fields.One2Many(
        'stock.forecast.line', 'forecast', 'Lines', states=STATES,
        depends=DEPENDS)
    company = fields.Many2One(
        'company.company', 'Company', required=True, states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines'))),
            },
        depends=['state', 'lines'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], 'State', readonly=True, select=True)

    def __init__(self):
        super(Forecast, self).__init__()
        self._sql_constraints += [
            ('check_from_to_date',
             'CHECK(to_date >= from_date)',
             '"To Date" must be greater than "From Date"!'),
            ]
        self._constraints += [
            ('check_date_overlap', 'date_overlap'),
            ]
        self._error_messages.update({
                'date_overlap': 'You can not create forecasts for the same ' \
                    'locations with overlapping dates',
                'delete_cancel': 'Forecast "%s" must be cancelled before '\
                    'deletion!',
                })
        self._order.insert(0, ('from_date', 'DESC'))
        self._order.insert(1, ('warehouse', 'ASC'))
        self._transitions |= set((
                ('draft', 'done'),
                ('draft', 'cancel'),
                ('done', 'draft'),
                ('cancel', 'draft'),
                ))
        self._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'draft',
                    },
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    },
                'confirm': {
                    'invisible': Eval('state') != 'draft',
                    },
                })

    def init(self, module_name):
        location_obj = Pool().get('stock.location')
        cursor = Transaction().cursor

        table = TableHandler(cursor, self, module_name)
        migrate_warehouse = (not table.column_exist('warehouse')
            and table.column_exist('location'))

        super(Forecast, self).init(module_name)

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

        if migrate_warehouse:
            location2warehouse = {}

            def find_warehouse(location):
                if location.type == 'warehouse':
                    return location.id
                elif location.parent:
                    return find_warehouse(location.parent)
            cursor.execute('SELECT id, location FROM "%s"' % self._table)
            for forecast_id, location_id in cursor.fetchall():
                warehouse_id = location_id  # default fallback
                if location_id in location2warehouse:
                    warehouse_id = location2warehouse[location_id]
                else:
                    location = location_obj.browse(location_id)
                    warehouse_id = find_warehouse(location) or location_id
                    location2warehouse[location_id] = warehouse_id
                cursor.execute('UPDATE "%s" SET warehouse = %%s '
                    'WHERE id = %%s' % self._table,
                    (warehouse_id, forecast_id))
            table.not_null_action('warehouse',
                action=self.warehouse.required and 'add' or 'remove')
            table.drop_column('location', True)

        # Migration from 2.0 delete stock moves
        forecast_ids = self.search([])
        self.delete_moves(forecast_ids)

    def default_state(self):
        return 'draft'

    def default_destination(self):
        location_obj = Pool().get('stock.location')
        location_ids = location_obj.search(
                self.destination.domain)
        if len(location_ids) == 1:
            return location_ids[0]

    def default_company(self):
        return Transaction().context.get('company')

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
                        'AND warehouse = %s ' \
                        'AND destination = %s ' \
                        'AND state = \'done\' ' \
                        'AND company = %s '
                        'AND id != %s',
                    (forecast.from_date, forecast.from_date,
                     forecast.to_date, forecast.to_date,
                     forecast.from_date, forecast.to_date,
                     forecast.warehouse.id, forecast.destination.id,
                     forecast.company.id, forecast.id))
            rowcount = cursor.rowcount
            if rowcount == -1 or rowcount is None:
                rowcount = len(cursor.fetchall())
            if rowcount:
                return False
        return True

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cancel before delete
        self.cancel(ids)
        for forecast in self.browse(ids):
            if forecast.state != 'cancel':
                self.raise_user_error('delete_cancel', forecast.rec_name)
        return super(Forecast, self).delete(ids)

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('done')
    def confirm(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        pass

    def create_moves(self, forecast_ids):
        'Create stock moves for the forecast ids'
        line_obj = Pool().get('stock.forecast.line')

        forecasts = self.browse(forecast_ids)
        for forecast in forecasts:
            if forecast.state == 'done':
                for line in forecast.lines:
                    line_obj.create_moves(line)

    def delete_moves(self, forecast_ids):
        'Delete stock moves for the forecast ids'
        line_obj = Pool().get('stock.forecast.line')

        forecasts = self.browse(forecast_ids)
        for forecast in forecasts:
            for line in forecast.lines:
                line_obj.delete_moves(line)

    def copy(self, ids, default=None):
        line_obj = Pool().get('stock.forecast.line')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if default is None:
            default = {}
        default = default.copy()
        default['lines'] = None

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
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ],
        on_change=['product'])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category',
            on_change_with=['product']),
        'get_product_uom_category')
    uom = fields.Many2One('product.uom', 'UOM', required=True,
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ], on_change=['uom'], depends=['product', 'product_uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
            'get_unit_digits')
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
        required=True, depends=['unit_digits'])
    minimal_quantity = fields.Float('Minimal Qty',
        digits=(16, Eval('unit_digits', 2)), required=True,
        depends=['unit_digits'])
    moves = fields.Many2Many('stock.forecast.line-stock.move',
        'line', 'move', 'Moves', readonly=True)
    forecast = fields.Many2One(
        'stock.forecast', 'Forecast', required=True, ondelete='CASCADE')
    quantity_executed = fields.Function(fields.Float('Quantity Executed',
            digits=(16, Eval('unit_digits', 2)), depends=['unit_digits']),
        'get_quantity_executed')

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
        product_obj = Pool().get('product.product')
        res = {}
        res['unit_digits'] = 2
        if vals.get('product'):
            product = product_obj.browse(vals['product'])
            res['uom'] = product.default_uom.id
            res['uom.rec_name'] = product.default_uom.rec_name
            res['unit_digits'] = product.default_uom.digits
        return res

    def on_change_with_product_uom_category(self, values):
        pool = Pool()
        product_obj = pool.get('product.product')
        if values.get('product'):
            product = product_obj.browse(values['product'])
            return product.default_uom_category.id

    def get_product_uom_category(self, ids, name):
        categories = {}
        for line in self.browse(ids):
            if line.product:
                categories[line.id] = line.product.default_uom_category.id
            else:
                categories[line.id] = None
        return categories

    def on_change_uom(self, vals):
        uom_obj = Pool().get('product.uom')
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

    def get_quantity_executed(self, ids, name):
        cursor = Transaction().cursor
        move_obj = Pool().get('stock.move')
        location_obj = Pool().get('stock.location')
        uom_obj = Pool().get('product.uom')
        forecast_obj = Pool().get('stock.forecast')
        line_move_obj = Pool().get('stock.forecast.line-stock.move')

        result = dict((x, 0) for x in ids)
        lines = self.browse(ids)
        key = lambda line: line.forecast.id
        lines.sort(key=key)
        for forecast_id, lines in itertools.groupby(lines, key):
            forecast = forecast_obj.browse(forecast_id)
            product2line = dict((line.product.id, line) for line in lines)
            product_ids = product2line.keys()
            for i in range(0, len(product_ids), cursor.IN_MAX):
                sub_ids = product_ids[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('product', sub_ids)
                cursor.execute('SELECT m.product, '
                        'SUM(m.internal_quantity) AS quantity '
                    'FROM "' + move_obj._table + '" AS m '
                        'JOIN "' + location_obj._table + '" AS fl '
                            'ON m.from_location = fl.id '
                        'JOIN "' + location_obj._table + '" AS tl '
                            'ON m.to_location = tl.id '
                        'LEFT JOIN "' + line_move_obj._table + '" AS lm '
                            'ON m.id = lm.move '
                    'WHERE ' + red_sql + ' '
                        'AND fl.left >= %s AND fl.right <= %s '
                        'AND tl.left >= %s AND tl.right <= %s '
                        'AND m.state != %s '
                        'AND COALESCE(m.effective_date, m.planned_date) >= %s '
                        'AND COALESCE(m.effective_date, m.planned_date) <= %s '
                        'AND lm.id IS NULL '
                    'GROUP BY m.product',
                    red_ids + [forecast.warehouse.left,
                        forecast.warehouse.right, forecast.destination.left,
                        forecast.destination.right, 'cancel',
                        forecast.from_date, forecast.to_date])
                for product_id, quantity in cursor.fetchall():
                    line = product2line[product_id]
                    result[line.id] = uom_obj.compute_qty(
                        line.product.default_uom, quantity, line.uom)
        return result

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = None
        return super(ForecastLine, self).copy(ids, default=default)

    def create_moves(self, line):
        'Create stock moves for the forecast line'
        move_obj = Pool().get('stock.move')
        uom_obj = Pool().get('product.uom')
        date_obj = Pool().get('ir.date')

        assert not line.moves

        today = date_obj.today()
        from_date = line.forecast.from_date
        if from_date < today:
            from_date = today
        to_date = line.forecast.to_date
        if to_date < today:
            return

        delta = to_date - from_date
        delta = delta.days + 1
        nb_packet = int((line.quantity - line.quantity_executed)
            / line.minimal_quantity)
        distribution = self.distribute(delta, nb_packet)
        unit_price = None
        if line.forecast.destination.type == 'customer':
            unit_price = line.product.list_price
            unit_price = uom_obj.compute_price(line.product.default_uom,
                    unit_price, line.uom)

        moves = []
        for day, qty in distribution.iteritems():
            if qty == 0.0:
                continue
            mid = move_obj.create({
                'from_location': line.forecast.warehouse.storage_location.id,
                'to_location': line.forecast.destination.id,
                'product': line.product.id,
                'uom': line.uom.id,
                'quantity': qty * line.minimal_quantity,
                'planned_date': (line.forecast.from_date
                        + datetime.timedelta(day)),
                'company': line.forecast.company.id,
                'currency': line.forecast.company.currency.id,
                'unit_price': unit_price,
                })
            moves.append(mid)
        self.write(line.id, {'moves': [('set', moves)]})

    def delete_moves(self, line):
        'Delete stock moves of the forecast line'
        move_obj = Pool().get('stock.move')
        move_obj.delete([m.id for m in line.moves])

    def distribute(self, delta, qty):
        'Distribute qty over delta'
        range_delta = range(delta)
        a = {}.fromkeys(range_delta, 0)
        while qty > 0:
            if qty > delta:
                for i in range_delta:
                    a[i] += qty // delta
                qty = qty % delta
            elif delta // qty > 1:
                i = 0
                while i < qty:
                    a[i * delta // qty + (delta // qty / 2)] += 1
                    i += 1
                qty = 0
            else:
                for i in range_delta:
                    a[i] += 1
                qty = delta - qty
                i = 0
                while i < qty:
                    a[delta - ((i * delta // qty) + (delta // qty / 2)) - 1
                        ] -= 1
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
            ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='CASCADE',
            select=True, required=True)

ForecastLineMove()


class ForecastCompleteAsk(ModelView):
    'Complete Forecast'
    _name = 'stock.forecast.complete.ask'
    _description = __doc__
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)

ForecastCompleteAsk()


class ForecastCompleteChoose(ModelView):
    'Complete Forecast'
    _name = 'stock.forecast.complete.choose'
    _description = __doc__
    products = fields.Many2Many('product.product', None, None, 'Products')

ForecastCompleteChoose()


class ForecastComplete(Wizard):
    'Complete Forecast'
    _name = 'stock.forecast.complete'
    start_state = 'ask'
    ask = StateView('stock.forecast.complete.ask',
        'stock_forecast.forecast_comlete_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Choose Products', 'choose', 'tryton-go-next'),
            Button('Complete', 'complete', 'tryton-ok', default=True),
            ])
    choose = StateView('stock.forecast.complete.choose',
        'stock_forecast.forecast_comlete_choose_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Choose Dates', 'ask', 'tryton-go-previous'),
            Button('Complete', 'complete', 'tryton-ok', default=True),
            ])
    complete = StateTransition()

    def __init__(self):
        super(ForecastComplete, self).__init__()
        self._error_messages.update({
            'from_to_date': '"From Date" should be smaller than "To Date"!',
            })

    def default_ask(self, session, fields):
        """
        Forecast dates shifted by one year.
        """
        forecast_obj = Pool().get('stock.forecast')
        forecast = forecast_obj.browse(Transaction().context['active_id'])

        res = {}
        for field in ("to_date", "from_date"):
            res[field] = forecast[field] - relativedelta(years=1)
        return res

    def _get_product_quantity(self, session):
        forecast_obj = Pool().get('stock.forecast')
        product_obj = Pool().get('product.product')
        forecast = forecast_obj.browse(Transaction().context['active_id'])
        if session.ask.from_date > session.ask.to_date:
            self.raise_user_error('from_to_date')

        with Transaction().set_context(
                stock_destination=[forecast.destination.id],
                stock_date_start=session.ask.from_date,
                stock_date_end=session.ask.to_date):
            return product_obj.products_by_location([forecast.warehouse.id],
                    with_childs=True, skip_zero=False)

    def default_choose(self, session, fields):
        """
        Collect products for which there is an outgoing stream between
        the given location and the destination.
        """
        if session.choose.products:
            return {'products': [x.id for x in session.choose.products]}
        pbl = self._get_product_quantity(session)
        products = []
        for (_, product), qty in pbl.iteritems():
            if qty < 0:
                products.append(product)
        return {'products': products}

    def transition_complete(self, session):
        pool = Pool()
        forecast_line_obj = pool.get('stock.forecast.line')
        product_obj = pool.get('product.product')

        prod2line = {}
        forecast_line_ids = forecast_line_obj.search([
                ('forecast', '=', Transaction().context['active_id']),
                ])
        for forecast_line in forecast_line_obj.browse(forecast_line_ids):
            prod2line[forecast_line.product.id] = forecast_line.id

        pbl = self._get_product_quantity(session)
        product_ids = [x[1] for x in pbl]
        prod2uom = {}
        for product in product_obj.browse(product_ids):
            prod2uom[product.id] = product.default_uom.id

        if session.choose.products:
            products = [x.id for x in session.choose.products]
        else:
            products = None

        for key, qty in pbl.iteritems():
            _, product = key
            if products and product not in products:
                continue
            if -qty <= 0:
                continue
            if product in prod2line:
                forecast_line_obj.write(prod2line[product], {
                        'product': product,
                        'quantity': -qty,
                        'uom': prod2uom[product],
                        'forecast': Transaction().context['active_id'],
                        'minimal_quantity': min(1, -qty),
                        })
            else:
                forecast_line_obj.create({
                        'product': product,
                        'quantity': -qty,
                        'uom': prod2uom[product],
                        'forecast': Transaction().context['active_id'],
                        'minimal_quantity': min(1, -qty),
                        })
        return 'end'

ForecastComplete()
