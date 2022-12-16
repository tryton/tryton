# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from dateutil.relativedelta import relativedelta
import itertools

from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, ModelSQL, fields, Unique
from trytond.model.exceptions import AccessError
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Not, Equal, Eval, Or, Bool, If
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import reduce_ids, grouped_slice

from .exceptions import ForecastValidationError


class Forecast(Workflow, ModelSQL, ModelView):
    "Stock Forecast"
    __name__ = "stock.forecast"

    _states = {
        'readonly': Not(Equal(Eval('state'), 'draft')),
    }
    _depends = ['state']

    warehouse = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'warehouse')], states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines', [0]))),
            },
        depends=['state'])
    destination = fields.Many2One(
        'stock.location', 'Destination', required=True,
        domain=[('type', 'in', ['customer', 'production'])], states=_states,
        depends=_depends)
    from_date = fields.Date(
        "From Date", required=True,
        domain=[('from_date', '<=', Eval('to_date'))],
        states=_states, depends=_depends + ['to_date'])
    to_date = fields.Date(
        "To Date", required=True,
        domain=[('to_date', '>=', Eval('from_date'))],
        states=_states, depends=_depends + ['from_date'])
    lines = fields.One2Many(
        'stock.forecast.line', 'forecast', 'Lines', states=_states,
        depends=_depends)
    company = fields.Many2One(
        'company.company', 'Company', required=True, states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines', [0]))),
            },
        depends=['state'])
    state = fields.Selection([
            ('draft', "Draft"),
            ('done', "Done"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, select=True)
    active = fields.Function(fields.Boolean('Active'),
        'get_active', searcher='search_active')

    del _states, _depends

    @classmethod
    def __setup__(cls):
        super(Forecast, cls).__setup__()
        cls._order.insert(0, ('from_date', 'DESC'))
        cls._order.insert(1, ('warehouse', 'ASC'))
        cls._transitions |= set((
                ('draft', 'done'),
                ('draft', 'cancelled'),
                ('done', 'draft'),
                ('cancelled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    'depends': ['state'],
                    },
                'confirm': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'complete': {
                    'readonly': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })
        cls._active_field = 'active'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        super(Forecast, cls).__register__(module_name)

        # Add index on create_date
        table = cls.__table_handler__(module_name)
        table.index_action('create_date', action='add')

        # Migration from 5.0: remove check_from_to_date
        table.drop_constraint('check_from_to_date')

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'cancel'))

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

    def get_rec_name(self, name):
        return self.warehouse.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('warehouse.rec_name',) + tuple(clause[1:])]

    @classmethod
    def validate(cls, forecasts):
        super(Forecast, cls).validate(forecasts)
        for forecast in forecasts:
            forecast.check_date_overlap()

    def check_date_overlap(self):
        if self.state != 'done':
            return
        transaction = Transaction()
        connection = transaction.connection
        transaction.database.lock(connection, self._table)
        forcast = self.__table__()
        cursor = connection.cursor()
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
            raise ForecastValidationError(
                gettext('stock_forecast.msg_forecast_date_overlap',
                    first=self.rec_name,
                    second=second.rec_name))

    @classmethod
    def delete(cls, forecasts):
        # Cancel before delete
        cls.cancel(forecasts)
        for forecast in forecasts:
            if forecast.state != 'cancelled':
                raise AccessError(
                    gettext('stock_forecast.msg_forecast_delete_cancel',
                        forecast=forecast.rec_name))
        super(Forecast, cls).delete(forecasts)

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
    @Workflow.transition('cancelled')
    def cancel(cls, forecasts):
        pass

    @classmethod
    @ModelView.button_action('stock_forecast.wizard_forecast_complete')
    def complete(cls, forecasts):
        pass

    @staticmethod
    def create_moves(forecasts):
        'Create stock moves for the forecast ids'
        pool = Pool()
        Line = pool.get('stock.forecast.line')
        to_save = []
        for forecast in forecasts:
            if forecast.state == 'done':
                for line in forecast.lines:
                    line.moves += tuple(line.get_moves())
                    to_save.append(line)
        Line.save(to_save)

    @staticmethod
    def delete_moves(forecasts):
        'Delete stock moves for the forecast ids'
        Line = Pool().get('stock.forecast.line')
        Line.delete_moves([l for f in forecasts for l in f.lines])


class ForecastLine(ModelSQL, ModelView):
    'Stock Forecast Line'
    __name__ = 'stock.forecast.line'
    _states = {
        'readonly': Eval('forecast_state') != 'draft',
        }
    _depends = ['forecast_state']

    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ],
        states=_states, depends=_depends)
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    uom = fields.Many2One('product.uom', 'UOM', required=True,
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        states=_states,
        depends=['product', 'product_uom_category'] + _depends)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
            'get_unit_digits')
    quantity = fields.Float(
        "Quantity", digits=(16, Eval('unit_digits', 2)), required=True,
        domain=[('quantity', '>=', 0)],
        states=_states, depends=['unit_digits'] + _depends)
    minimal_quantity = fields.Float(
        "Minimal Qty", digits=(16, Eval('unit_digits', 2)), required=True,
        domain=[('minimal_quantity', '<=', Eval('quantity'))],
        states=_states, depends=['unit_digits', 'quantity'] + _depends)
    moves = fields.Many2Many('stock.forecast.line-stock.move',
        'line', 'move', 'Moves', readonly=True)
    forecast = fields.Many2One(
        'stock.forecast', 'Forecast', required=True, ondelete='CASCADE',
        states={
            'readonly': ((Eval('forecast_state') != 'draft')
                & Bool(Eval('forecast'))),
            },
        depends=['forecast_state'])
    forecast_state = fields.Function(
        fields.Selection('get_forecast_states', 'Forecast State'),
        'on_change_with_forecast_state')
    quantity_executed = fields.Function(fields.Float('Quantity Executed',
            digits=(16, Eval('unit_digits', 2)), depends=['unit_digits']),
        'get_quantity_executed')

    del _states, _depends

    @classmethod
    def __setup__(cls):
        super(ForecastLine, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('forecast_product_uniq', Unique(t, t.forecast, t.product),
                'stock_forecast.msg_forecast_line_product_unique'),
            ]

    @classmethod
    def __register__(cls, module_name):
        super().__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 5.0: remove check on quantity
        table_h.drop_constraint('check_line_qty_pos')
        table_h.drop_constraint('check_line_minimal_qty')

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
    def get_forecast_states(cls):
        pool = Pool()
        Forecast = pool.get('stock.forecast')
        return Forecast.fields_get(['state'])['state']['selection']

    @fields.depends('forecast', '_parent_forecast.state')
    def on_change_with_forecast_state(self, name=None):
        if self.forecast:
            return self.forecast.state

    def get_rec_name(self, name):
        return self.product.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name',) + tuple(clause[1:])]

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

        def key(line):
            return line.forecast.id
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
                        & (move.state != 'cancelled')
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
        else:
            default = default.copy()
        default.setdefault('moves', None)
        return super(ForecastLine, cls).copy(lines, default=default)

    def get_moves(self):
        'Get stock moves for the forecast line'
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
            return []

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

        moves = []
        for day, qty in distribution.items():
            if qty == 0.0:
                continue
            move = Move()
            move.from_location = self.forecast.warehouse.storage_location
            move.to_location = self.forecast.destination
            move.product = self.product
            move.uom = self.uom
            move.quantity = qty * self.minimal_quantity
            move.planned_date = from_date + datetime.timedelta(day)
            move.company = self.forecast.company
            move.currency = self.forecast.company.currency
            move.unit_price = unit_price
            moves.append(move)
        return moves

    @classmethod
    def delete_moves(cls, lines):
        'Delete stock moves of the forecast line'
        Move = Pool().get('stock.move')
        Move.delete([m for l in lines for m in l.moves])

    def distribute(self, delta, qty):
        'Distribute qty over delta'
        range_delta = list(range(delta))
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
    from_date = fields.Date(
        "From Date", required=True,
        domain=[('from_date', '<', Eval('to_date'))],
        depends=['to_date'])
    to_date = fields.Date(
        "To Date", required=True,
        domain=[('to_date', '>', Eval('from_date'))],
        depends=['from_date'])


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
            Button('Choose Products', 'choose', 'tryton-forward'),
            Button('Complete', 'complete', 'tryton-ok', default=True),
            ])
    choose = StateView('stock.forecast.complete.choose',
        'stock_forecast.forecast_complete_choose_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Choose Dates', 'ask', 'tryton-back'),
            Button('Complete', 'complete', 'tryton-ok', default=True),
            ])
    complete = StateTransition()

    def default_ask(self, fields):
        """
        Forecast dates shifted by one year.
        """
        default = {}
        for field in ("to_date", "from_date"):
            default[field] = (
                getattr(self.record, field) - relativedelta(years=1))
        return default

    def _get_product_quantity(self):
        pool = Pool()
        Product = pool.get('product.product')

        with Transaction().set_context(
                stock_destinations=[self.record.destination.id],
                stock_date_start=self.ask.from_date,
                stock_date_end=self.ask.to_date):
            return Product.products_by_location([self.record.warehouse.id],
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
        for (_, product), qty in pbl.items():
            if qty < 0:
                products.append(product)
        return {'products': products}

    def transition_complete(self):
        pool = Pool()
        ForecastLine = pool.get('stock.forecast.line')
        Product = pool.get('product.product')

        forecast = self.record
        prod2line = {}
        forecast_lines = ForecastLine.search([
                ('forecast', '=', forecast.id),
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

        to_save = []
        for key, qty in pbl.items():
            _, product = key
            if products and product not in products:
                continue
            if -qty <= 0:
                continue
            if product in prod2line:
                line = prod2line[product]
            else:
                line = ForecastLine()
            line.product = product
            line.quantity = -qty
            line.uom = prod2uom[product]
            line.forecast = forecast
            line.minimal_quantity = min(1, -qty)
            to_save.append(line)

        ForecastLine.save(to_save)
        return 'end'
