# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import division
import datetime
from dateutil.relativedelta import relativedelta
import itertools

from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import ModelView, Workflow, ModelSQL, fields, Check, Unique
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Not, Equal, Eval, Or, Bool, If
from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import reduce_ids, grouped_slice

__all__ = ['Forecast', 'ForecastLine', 'ForecastLineMove',
    'ForecastCompleteAsk', 'ForecastCompleteChoose', 'ForecastComplete']

STATES = {
    'readonly': Not(Equal(Eval('state'), 'draft')),
}
DEPENDS = ['state']


class Forecast(Workflow, ModelSQL, ModelView):
    "Stock Forecast"
    __name__ = "stock.forecast"
    _rec_name = 'warehouse'
    warehouse = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'warehouse')], states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines', [0]))),
            },
        depends=['state'])
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
                Bool(Eval('lines', [0]))),
            },
        depends=['state'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], 'State', readonly=True, select=True)
    active = fields.Function(fields.Boolean('Active'),
        'get_active', searcher='search_active')

    @classmethod
    def __setup__(cls):
        super(Forecast, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_from_to_date', Check(t, t.to_date >= t.from_date),
                '"To Date" must be greater than "From Date"'),
            ]
        cls._error_messages.update({
                'date_overlap': ('Forecast "%(first)s" overlaps with dates '
                    'of forecast "%(second)s" in the same location.'),
                'delete_cancel': ('Forecast "%s" must be cancelled before '
                    'deletion.'),
                })
        cls._order.insert(0, ('from_date', 'DESC'))
        cls._order.insert(1, ('warehouse', 'ASC'))
        cls._transitions |= set((
                ('draft', 'done'),
                ('draft', 'cancel'),
                ('done', 'draft'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'draft',
                    },
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    },
                'confirm': {
                    'invisible': Eval('state') != 'draft',
                    },
                'complete': {
                    'readonly': Eval('state') != 'draft',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        Location = Pool().get('stock.location')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        table = TableHandler(cls, module_name)
        migrate_warehouse = (not table.column_exist('warehouse')
            and table.column_exist('location'))

        super(Forecast, cls).__register__(module_name)

        # Add index on create_date
        table = TableHandler(cls, module_name)
        table.index_action('create_date', action='add')

        if migrate_warehouse:
            location2warehouse = {}

            def find_warehouse(location):
                if location.type == 'warehouse':
                    return location.id
                elif location.parent:
                    return find_warehouse(location.parent)
            cursor.execute(*sql_table.select(sql_table.id, sql_table.location))
            for forecast_id, location_id in cursor.fetchall():
                warehouse_id = location_id  # default fallback
                if location_id in location2warehouse:
                    warehouse_id = location2warehouse[location_id]
                else:
                    location = Location(location_id)
                    warehouse_id = find_warehouse(location) or location_id
                    location2warehouse[location_id] = warehouse_id
                cursor.execute(*sql_table.update(
                        columns=[sql_table.warehouse],
                        values=[warehouse_id],
                        where=sql_table.id == forecast_id))
            table.not_null_action('warehouse',
                action=cls.warehouse.required and 'add' or 'remove')
            table.drop_column('location', True)

        # Migration from 2.0 delete stock moves
        forecasts = cls.search([])
        cls.delete_moves(forecasts)

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_destination(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.destination.domain)
        if len(locations) == 1:
            return locations[0].id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_active(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        return self.to_date >= Date.today()

    @classmethod
    def search_active(cls, name, clause):
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        operators = {
            '=': '>=',
            '!=': '<',
            }
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[1] in operators:
            if clause[2]:
                return [('to_date', operators[clause[1]], today)]
            else:
                return [('to_date', operators[reverse[clause[1]]], today)]
        else:
            return []

    @classmethod
    def validate(cls, forecasts):
        super(Forecast, cls).validate(forecasts)
        for forecast in forecasts:
            forecast.check_date_overlap()

    def check_date_overlap(self):
        cursor = Transaction().connection.cursor()
        if self.state != 'done':
            return
        forcast = self.__table__()
        cursor.execute(*forcast.select(forcast.id,
                where=(((forcast.from_date <= self.from_date)
                        & (forcast.to_date >= self.from_date))
                    | ((forcast.from_date <= self.to_date)
                        & (forcast.to_date >= self.to_date))
                    | ((forcast.from_date >= self.from_date)
                        & (forcast.to_date <= self.to_date)))
                & (forcast.warehouse == self.warehouse.id)
                & (forcast.destination == self.destination.id)
                & (forcast.company == self.company.id)
                & (forcast.id != self.id)))
        forecast_id = cursor.fetchone()
        if forecast_id:
            second = self.__class__(forecast_id[0])
            self.raise_user_error('date_overlap', {
                    'first': self.rec_name,
                    'second': second.rec_name,
                    })

    @classmethod
    def delete(self, forecasts):
        # Cancel before delete
        self.cancel(forecasts)
        for forecast in forecasts:
            if forecast.state != 'cancel':
                self.raise_user_error('delete_cancel', forecast.rec_name)
        super(Forecast, self).delete(forecasts)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, forecasts):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def confirm(cls, forecasts):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, forecasts):
        pass

    @classmethod
    @ModelView.button_action('stock_forecast.wizard_forecast_complete')
    def complete(cls, forecasts):
        pass

    @staticmethod
    def create_moves(forecasts):
        'Create stock moves for the forecast ids'
        for forecast in forecasts:
            if forecast.state == 'done':
                for line in forecast.lines:
                    line.create_moves()

    @staticmethod
    def delete_moves(forecasts):
        'Delete stock moves for the forecast ids'
        Line = Pool().get('stock.forecast.line')
        Line.delete_moves([l for f in forecasts for l in f.lines])

    @classmethod
    def copy(cls, forecasts, default=None):
        Line = Pool().get('stock.forecast.line')

        if default is None:
            default = {}
        default = default.copy()
        default['lines'] = None

        new_forecasts = []
        for forecast in forecasts:
            new_forecast, = super(Forecast, cls).copy([forecast],
                default=default)
            Line.copy([x for x in forecast.lines],
                default={
                    'forecast': new_forecast.id,
                    })
            new_forecasts.append(new_forecast)
        return new_forecasts


class ForecastLine(ModelSQL, ModelView):
    'Stock Forecast Line'
    __name__ = 'stock.forecast.line'
    _rec_name = 'product'
    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    uom = fields.Many2One('product.uom', 'UOM', required=True,
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ], depends=['product', 'product_uom_category'])
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

    @classmethod
    def __setup__(cls):
        super(ForecastLine, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_line_qty_pos', Check(t, t.quantity >= 0),
                'Line quantity must be positive'),
            ('check_line_minimal_qty',
                Check(t, t.quantity >= t.minimal_quantity),
                'Line quantity must be greater than the minimal quantity'),
            ('forecast_product_uniq', Unique(t, t.forecast, t.product),
                'Product must be unique by forecast'),
            ]

    @staticmethod
    def default_unit_digits():
        return 2

    @staticmethod
    def default_minimal_quantity():
        return 1.0

    @fields.depends('product')
    def on_change_product(self):
        self.unit_digits = 2
        if self.product:
            self.uom = self.product.default_uom
            self.unit_digits = self.product.default_uom.digits

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends('uom')
    def on_change_uom(self):
        self.unit_digits = 2
        if self.uom:
            self.unit_digits = self.uom.digits

    def get_unit_digits(self, name):
        return self.product.default_uom.digits

    @classmethod
    def get_quantity_executed(cls, lines, name):
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Move = pool.get('stock.move')
        Location = pool.get('stock.location')
        Uom = pool.get('product.uom')
        Forecast = pool.get('stock.forecast')
        LineMove = pool.get('stock.forecast.line-stock.move')

        move = Move.__table__()
        location_from = Location.__table__()
        location_to = Location.__table__()
        line_move = LineMove.__table__()

        result = dict((x.id, 0) for x in lines)
        key = lambda line: line.forecast.id
        lines.sort(key=key)
        for forecast_id, lines in itertools.groupby(lines, key):
            forecast = Forecast(forecast_id)
            product2line = dict((line.product.id, line) for line in lines)
            product_ids = product2line.keys()
            for sub_ids in grouped_slice(product_ids):
                red_sql = reduce_ids(move.product, sub_ids)
                cursor.execute(*move.join(location_from,
                        condition=move.from_location == location_from.id
                        ).join(location_to,
                        condition=move.to_location == location_to.id
                        ).join(line_move, 'LEFT',
                        condition=move.id == line_move.move
                        ).select(move.product, Sum(move.internal_quantity),
                        where=red_sql
                        & (location_from.left >= forecast.warehouse.left)
                        & (location_from.right <= forecast.warehouse.right)
                        & (location_to.left >= forecast.destination.left)
                        & (location_to.right <= forecast.destination.right)
                        & (move.state != 'cancel')
                        & (Coalesce(move.effective_date, move.planned_date)
                            >= forecast.from_date)
                        & (Coalesce(move.effective_date, move.planned_date)
                            <= forecast.to_date)
                        & (line_move.id == Null),
                        group_by=move.product))
                for product_id, quantity in cursor.fetchall():
                    line = product2line[product_id]
                    result[line.id] = Uom.compute_qty(line.product.default_uom,
                        quantity, line.uom)
        return result

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = None
        return super(ForecastLine, cls).copy(lines, default=default)

    def create_moves(self):
        'Create stock moves for the forecast line'
        pool = Pool()
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')
        Date = pool.get('ir.date')

        assert not self.moves

        today = Date.today()
        from_date = self.forecast.from_date
        if from_date < today:
            from_date = today
        to_date = self.forecast.to_date
        if to_date < today:
            return

        delta = to_date - from_date
        delta = delta.days + 1
        nb_packet = ((self.quantity - self.quantity_executed)
            // self.minimal_quantity)
        distribution = self.distribute(delta, nb_packet)
        unit_price = None
        if self.forecast.destination.type == 'customer':
            unit_price = self.product.list_price
            unit_price = Uom.compute_price(self.product.default_uom,
                unit_price, self.uom)

        to_create = []
        for day, qty in distribution.iteritems():
            if qty == 0.0:
                continue
            to_create.append({
                    'from_location': (
                        self.forecast.warehouse.storage_location.id),
                    'to_location': self.forecast.destination.id,
                    'product': self.product.id,
                    'uom': self.uom.id,
                    'quantity': qty * self.minimal_quantity,
                    'planned_date': (self.forecast.from_date
                        + datetime.timedelta(day)),
                    'company': self.forecast.company.id,
                    'currency': self.forecast.company.currency.id,
                    'unit_price': unit_price,
                    })
        moves = []
        if to_create:
            moves = Move.create(to_create)
        self.write([self], {'moves': [('add', [m.id for m in moves])]})

    @classmethod
    def delete_moves(cls, lines):
        'Delete stock moves of the forecast line'
        Move = Pool().get('stock.move')
        Move.delete([m for l in lines for m in l.moves])

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
                    a[i * delta // qty + (delta // qty // 2)] += 1
                    i += 1
                qty = 0
            else:
                for i in range_delta:
                    a[i] += 1
                qty = delta - qty
                i = 0
                while i < qty:
                    a[delta - ((i * delta // qty) + (delta // qty // 2)) - 1
                        ] -= 1
                    i += 1
                qty = 0
        return a


class ForecastLineMove(ModelSQL):
    'ForecastLine - Move'
    __name__ = 'stock.forecast.line-stock.move'
    _table = 'forecast_line_stock_move_rel'
    line = fields.Many2One('stock.forecast.line', 'Forecast Line',
            ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='CASCADE',
            select=True, required=True)


class ForecastCompleteAsk(ModelView):
    'Complete Forecast'
    __name__ = 'stock.forecast.complete.ask'
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)


class ForecastCompleteChoose(ModelView):
    'Complete Forecast'
    __name__ = 'stock.forecast.complete.choose'
    products = fields.Many2Many('product.product', None, None, 'Products')


class ForecastComplete(Wizard):
    'Complete Forecast'
    __name__ = 'stock.forecast.complete'
    start_state = 'ask'
    ask = StateView('stock.forecast.complete.ask',
        'stock_forecast.forecast_complete_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Choose Products', 'choose', 'tryton-go-next'),
            Button('Complete', 'complete', 'tryton-ok', default=True),
            ])
    choose = StateView('stock.forecast.complete.choose',
        'stock_forecast.forecast_complete_choose_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Choose Dates', 'ask', 'tryton-go-previous'),
            Button('Complete', 'complete', 'tryton-ok', default=True),
            ])
    complete = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ForecastComplete, cls).__setup__()
        cls._error_messages.update({
                'from_to_date': (
                    '"From Date" should be smaller than "To Date".'),
                })

    def default_ask(self, fields):
        """
        Forecast dates shifted by one year.
        """
        Forecast = Pool().get('stock.forecast')
        forecast = Forecast(Transaction().context['active_id'])

        res = {}
        for field in ("to_date", "from_date"):
            res[field] = getattr(forecast, field) - relativedelta(years=1)
        return res

    def _get_product_quantity(self):
        pool = Pool()
        Forecast = pool.get('stock.forecast')
        Product = pool.get('product.product')
        forecast = Forecast(Transaction().context['active_id'])
        if self.ask.from_date > self.ask.to_date:
            self.raise_user_error('from_to_date')

        with Transaction().set_context(
                stock_destinations=[forecast.destination.id],
                stock_date_start=self.ask.from_date,
                stock_date_end=self.ask.to_date):
            return Product.products_by_location([forecast.warehouse.id],
                with_childs=True)

    def default_choose(self, fields):
        """
        Collect products for which there is an outgoing stream between
        the given location and the destination.
        """
        if getattr(self.choose, 'products', None):
            return {'products': [x.id for x in self.choose.products]}
        pbl = self._get_product_quantity()
        products = []
        for (_, product), qty in pbl.iteritems():
            if qty < 0:
                products.append(product)
        return {'products': products}

    def transition_complete(self):
        pool = Pool()
        ForecastLine = pool.get('stock.forecast.line')
        Product = pool.get('product.product')

        prod2line = {}
        forecast_lines = ForecastLine.search([
                ('forecast', '=', Transaction().context['active_id']),
                ])
        for forecast_line in forecast_lines:
            prod2line[forecast_line.product.id] = forecast_line

        pbl = self._get_product_quantity()
        product_ids = [x[1] for x in pbl]
        prod2uom = {}
        for product in Product.browse(product_ids):
            prod2uom[product.id] = product.default_uom.id

        if getattr(self.choose, 'products', None):
            products = [x.id for x in self.choose.products]
        else:
            products = None

        to_create = []
        for key, qty in pbl.iteritems():
            _, product = key
            if products and product not in products:
                continue
            if -qty <= 0:
                continue
            if product in prod2line:
                ForecastLine.write([prod2line[product]], {
                        'product': product,
                        'quantity': -qty,
                        'uom': prod2uom[product],
                        'forecast': Transaction().context['active_id'],
                        'minimal_quantity': min(1, -qty),
                        })
            else:
                to_create.append({
                        'product': product,
                        'quantity': -qty,
                        'uom': prod2uom[product],
                        'forecast': Transaction().context['active_id'],
                        'minimal_quantity': min(1, -qty),
                        })
        if to_create:
            ForecastLine.create(to_create)
        return 'end'
