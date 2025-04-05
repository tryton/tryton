# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
import itertools

from dateutil.relativedelta import relativedelta
from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.operators import Equal

from trytond.i18n import gettext
from trytond.model import (
    Exclude, Index, ModelSQL, ModelView, Unique, Workflow, fields)
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.sql.functions import DateRange
from trytond.sql.operators import RangeOverlap
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard


class Forecast(Workflow, ModelSQL, ModelView):
    __name__ = "stock.forecast"

    _states = {
        'readonly': Eval('state') != 'draft',
    }

    warehouse = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'warehouse')], states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            })
    destination = fields.Many2One(
        'stock.location', 'Destination', required=True,
        domain=[('type', 'in', ['customer', 'production'])], states=_states)
    from_date = fields.Date(
        "From Date", required=True,
        domain=[('from_date', '<=', Eval('to_date'))],
        states=_states)
    to_date = fields.Date(
        "To Date", required=True,
        domain=[('to_date', '>=', Eval('from_date'))],
        states=_states)
    lines = fields.One2Many(
        'stock.forecast.line', 'forecast', 'Lines', states=_states)
    company = fields.Many2One(
        'company.company', 'Company', required=True, states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            })
    state = fields.Selection([
            ('draft', "Draft"),
            ('done', "Done"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, sort=False)
    active = fields.Function(fields.Boolean('Active'),
        'get_active', searcher='search_active')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('dates_done_overlap',
                Exclude(t,
                    (t.company, Equal),
                    (t.warehouse, Equal),
                    (t.destination, Equal),
                    (DateRange(t.from_date, t.to_date, '[]'), RangeOverlap),
                    where=t.state == 'done'),
                'stock_forecast.msg_forecast_done_dates_overlap'),
            ]
        cls._sql_indexes.add(
            Index(
                t,
                (t.state, Index.Equality(cardinality='low')),
                (t.to_date, Index.Range())))
        cls.create_date.select = True
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

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_warehouse(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        return Location.get_default_warehouse()

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
        pool = Pool()
        Lang = pool.get('ir.lang')

        lang = Lang.get()
        from_date = lang.strftime(self.from_date)
        to_date = lang.strftime(self.to_date)
        return (
            f'{self.warehouse.rec_name} → {self.destination.rec_name} @ '
            f'[{from_date} - {to_date}]')

    @classmethod
    def search_rec_name(cls, name, clause):
        operator = clause[1]
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('warehouse.rec_name', *clause[1:]),
            ('destination.rec_name', *clause[1:]),
            ]

    @classmethod
    def check_modification(cls, mode, forecasts, values=None, external=False):
        super().check_modification(
            mode, forecasts, values=values, external=external)
        if mode == 'delete':
            for forecast in forecasts:
                if forecast.state not in {'cancelled', 'draft'}:
                    raise AccessError(gettext(
                            'stock_forecast.msg_forecast_delete_cancel',
                            forecast=forecast.rec_name))

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
        Move = pool.get('stock.move')
        to_save = []
        for forecast in forecasts:
            if forecast.state == 'done':
                for line in forecast.lines:
                    to_save.extend(line.get_moves())
        Move.save(to_save)

    @staticmethod
    def delete_moves(forecasts):
        'Delete stock moves for the forecast ids'
        Line = Pool().get('stock.forecast.line')
        Line.delete_moves([l for f in forecasts for l in f.lines])


class ForecastLine(ModelSQL, ModelView):
    __name__ = 'stock.forecast.line'
    _states = {
        'readonly': Eval('forecast_state') != 'draft',
        }

    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ],
        states=_states)
    product_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product UoM Category",
            help="The category of Unit of Measure for the product."),
        'on_change_with_product_uom_category')
    unit = fields.Many2One(
        'product.uom', "Unit", required=True,
        domain=[
            If(Eval('product_uom_category'),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        states=_states,
        depends={'product'})
    quantity = fields.Float(
        "Quantity", digits='unit', required=True,
        domain=[('quantity', '>=', 0)],
        states=_states)
    minimal_quantity = fields.Float(
        "Minimal Qty", digits='unit', required=True,
        domain=[('minimal_quantity', '<=', Eval('quantity'))],
        states=_states)
    moves = fields.One2Many('stock.move', 'origin', "Moves", readonly=True)
    forecast = fields.Many2One(
        'stock.forecast', 'Forecast', required=True, ondelete='CASCADE',
        states={
            'readonly': (Eval('forecast_state') != 'draft') & Eval('forecast'),
            })
    forecast_state = fields.Function(
        fields.Selection('get_forecast_states', 'Forecast State'),
        'on_change_with_forecast_state')
    quantity_executed = fields.Function(fields.Float(
            "Quantity Executed", digits='unit'), 'get_quantity_executed')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('forecast')
        t = cls.__table__()
        cls._sql_constraints += [
            ('forecast_product_uniq', Unique(t, t.forecast, t.product),
                'stock_forecast.msg_forecast_line_product_unique'),
            ]

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        # Migration from 6.8: rename uom to unit
        if (table_h.column_exist('uom')
                and not table_h.column_exist('unit')):
            table_h.column_rename('uom', 'unit')

        super().__register__(module_name)

    @staticmethod
    def default_minimal_quantity():
        return 1.0

    @fields.depends('product')
    def on_change_product(self):
        if self.product:
            self.unit = self.product.default_uom

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        return self.product.default_uom_category if self.product else None

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

        move = Move.__table__()
        location_from = Location.__table__()
        location_to = Location.__table__()

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
                        & ((move.origin == Null)
                            | ~move.origin.like('stock.forecast.line,%')),
                        group_by=move.product))
                for product_id, quantity in cursor:
                    line = product2line[product_id]
                    result[line.id] = Uom.compute_qty(
                        line.product.default_uom, quantity, line.unit)
        return result

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('moves', None)
        return super().copy(lines, default=default)

    def get_moves(self):
        'Get stock moves for the forecast line'
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')

        assert not self.moves

        today = Date.today()
        from_date = self.forecast.from_date
        if from_date < today:
            from_date = today
        to_date = self.forecast.to_date
        if to_date < today:
            return []
        if self.quantity_executed >= self.quantity:
            return []

        delta = to_date - from_date
        delta = delta.days + 1
        nb_packet = ((self.quantity - self.quantity_executed)
            // self.minimal_quantity)
        distribution = self.distribute(delta, nb_packet)

        moves = []
        for day, qty in distribution.items():
            if qty == 0.0:
                continue
            move = Move()
            move.from_location = self.forecast.warehouse.storage_location
            move.to_location = self.forecast.destination
            move.product = self.product
            move.unit = self.unit
            move.quantity = qty * self.minimal_quantity
            move.planned_date = from_date + datetime.timedelta(day)
            move.company = self.forecast.company
            move.currency = self.forecast.company.currency
            move.unit_price = (
                0 if self.forecast.destination.type == 'customer' else None)
            move.origin = self
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


class ForecastCompleteAsk(ModelView):
    __name__ = 'stock.forecast.complete.ask'
    company = fields.Many2One('company.company', "Company", readonly=True)
    warehouse = fields.Many2One('stock.location', "Warehouse", readonly=True)
    destination = fields.Many2One(
        'stock.location', "Destination", readonly=True)
    from_date = fields.Date(
        "From Date", required=True,
        domain=[('from_date', '<', Eval('to_date'))],
        states={
            'readonly': Bool(Eval('products')),
            })
    to_date = fields.Date(
        "To Date", required=True,
        domain=[('to_date', '>', Eval('from_date'))],
        states={
            'readonly': Bool(Eval('products')),
            })
    products = fields.Many2Many(
        'product.product', None, None, "Products",
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ],
        context={
            'company': Eval('company', -1),
            'locations': [Eval('warehouse', -1)],
            'stock_destinations': [Eval('destination', -1)],
            'stock_date_start': Eval('from_date', None),
            'stock_date_end': Eval('to_date', None),
            'with_childs': True,
            'stock_invert': True,
            },
        depends=[
            'company', 'warehouse', 'destination', 'from_date', 'to_date'])


class ForecastComplete(Wizard):
    __name__ = 'stock.forecast.complete'
    start_state = 'ask'
    ask = StateView('stock.forecast.complete.ask',
        'stock_forecast.forecast_complete_ask_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Complete", 'complete', 'tryton-ok', default=True),
            ])
    complete = StateTransition()

    def default_ask(self, fields):
        """
        Forecast dates shifted by one year.
        """
        default = {}
        for field in ['company', 'warehouse', 'destination']:
            if field in fields:
                record = getattr(self.record, field)
                default[field] = record.id
        for field in ["to_date", "from_date"]:
            if field in fields:
                default[field] = (
                    getattr(self.record, field) - relativedelta(years=1))
        return default

    def transition_complete(self):
        pool = Pool()
        ForecastLine = pool.get('stock.forecast.line')

        product2line = {l.product: l for l in self.record.lines}
        to_save = []
        # Ensure context is set
        self.ask.products = map(int, self.ask.products)
        for product in self.ask.products:
            line = product2line.get(product, ForecastLine())
            self._fill_line(line, product)
            to_save.append(line)
        ForecastLine.save(to_save)
        return 'end'

    def _fill_line(self, line, product):
        quantity = max(product.quantity, 0)
        line.product = product
        line.quantity = quantity
        line.unit = product.default_uom
        line.forecast = self.record
        line.minimal_quantity = min(1, quantity)
