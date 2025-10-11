# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

from dateutil.relativedelta import relativedelta
from sql import Literal, Null, Window
from sql.aggregate import Min, Sum
from sql.conditionals import Case, Coalesce, Greatest, Least, NullIf
from sql.functions import Function, NthValue, Round
from sql.operators import Concat

from trytond import backend
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class _SQLite_JulianDay(Function):
    __slots__ = ()
    _function = 'JULIANDAY'


class _InventoryContextMixin(ModelView):

    company = fields.Many2One('company.company', "Company", required=True)
    location = fields.Many2One(
        'stock.location', "Location", required=True,
        domain=[
            ('type', 'in', ['warehouse', 'storage', 'view']),
            ])

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_location(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        return Transaction().context.get(
            'location', Location.get_default_warehouse())


class _InventoryMixin:
    __slots__ = ()

    company = fields.Many2One('company.company', "Company")
    product = fields.Reference("Product", [
            ('product.product', "Variant"),
            ('product.template', "Product"),
            ])
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"),
        'on_change_with_unit')

    input_quantity = fields.Float("Input Quantity")
    output_quantity = fields.Float("Output Quantity")
    quantity = fields.Float("Quantity")

    @classmethod
    def table_query(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Period = pool.get('stock.period')
        PeriodCache = pool.get('stock.period.cache')
        Product = pool.get('product.product')

        transaction = Transaction()
        context = transaction.context
        move = Move.__table__()
        from_location = Location.__table__()
        to_location = Location.__table__()
        period_cache = PeriodCache.__table__()
        product_table = Product.__table__()

        if location := context.get('location'):
            location = Location(location)
            left, right = location.left, location.right
        else:
            left = right = -1
        if date := context.get('date'):
            from_date = to_date = date
        else:
            from_date = context.get('from_date') or dt.date.min
            to_date = context.get('to_date') or dt.date.max
        company = context.get('company')

        if periods := Period.search([
                    ('company', '=', company),
                    ('date', '<=', from_date),
                    ('state', '=', 'closed'),
                    ],
                order=[('date', 'DESC')],
                limit=1):
            period, = periods
        else:
            period = None

        quantities = (
            move
            .join(from_location,
                condition=move.from_location == from_location.id)
            .join(to_location,
                condition=move.to_location == to_location.id)
            )

        if context.get('product_type') == 'product.product':
            product = Concat('product.product,', move.product)
        else:
            product = Concat('product.template,', product_table.template)
            quantities = (
                quantities
                .join(product_table,
                    condition=move.product == product_table.id)
                )

        move_date = Coalesce(move.effective_date, move.planned_date)
        input_clause = (
            (to_location.left >= left) & (to_location.right <= right))
        output_clause = (
            (from_location.left >= left) & (from_location.right <= right))
        start_quantity = Sum(
            move.quantity * Case((output_clause, -1), else_=1),
            filter_=(move_date < from_date))
        input_quantity = Sum(
            move.quantity,
            filter_=input_clause & (move_date >= from_date))
        output_quantity = Sum(
            move.quantity,
            filter_=output_clause & (move_date >= from_date))

        date_column = Greatest(move_date, from_date)
        if context.get('product_type') == 'product.product':
            partition = [move.product]
        else:
            partition = [product_table.template]

        # Use NthValue instead of LastValue to get NULL for the last row
        next_date_column = NthValue(
            date_column, 2, window=Window(
                partition,
                order_by=[date_column.asc],
                frame='ROWS', start=0, end=1))

        state_clause = cls._state_clause(move, to_date)

        quantities = quantities.select(
            Min(move.id).as_('id'),
            product.as_('product'),
            date_column.as_('date'),
            next_date_column.as_('next_date'),
            start_quantity.as_('start_quantity'),
            input_quantity.as_('input_quantity'),
            output_quantity.as_('output_quantity'),
            *cls._quantities_columns(move, product_table),
            where=(((input_clause & ~output_clause)
                    | (output_clause & ~input_clause))
                & (move_date <= to_date)
                & state_clause
                & (move.company == company)),
            group_by=[
                *partition,
                date_column,
                *cls._quantities_group_by(move, product_table),
                ],
            )

        quantity = Sum(
            Coalesce(quantities.start_quantity, 0)
            + Coalesce(quantities.input_quantity, 0)
            - Coalesce(quantities.output_quantity, 0),
            window=Window(
                [quantities.product],
                order_by=[*cls._quantities_order_by(quantities)]))

        if period:
            quantities.where &= move_date > period.date
            if context.get('product_type') != 'product.product':
                period_cache_product = Product.__table__()
                cache = (
                    period_cache
                    .join(period_cache_product,
                        condition=period_cache.product
                        == period_cache_product.id)
                    .select(
                        period_cache_product.template.as_('product'),
                        Sum(period_cache.internal_quantity
                            ).as_('quantity'),
                        group_by=[period_cache_product.template]))
            else:
                cache = (
                    period_cache
                    .select(
                        period_cache.product.as_('product'),
                        Sum(period_cache.internal_quantity).as_('quantity'),
                        group_by=[period_cache.product]))
            location_cache = Location.__table__()
            cache.where = (
                (period_cache.period == period.id)
                & period_cache.location.in_(
                    location_cache.select(
                        location_cache.id,
                        where=(location_cache.left >= left)
                        & (location_cache.right <= right))))
            query = quantities.join(cache, 'LEFT',
                condition=(
                    cache.product
                    == cls.product.sql_id(quantities.product, cls)))
            quantity += Coalesce(cache.quantity, 0)
        else:
            query = quantities

        return (query
            .select(
                quantities.id.as_('id'),
                Literal(company).as_('company'),
                quantities.product.as_('product'),
                quantities.input_quantity.as_('input_quantity'),
                quantities.output_quantity.as_('output_quantity'),
                quantity.as_('quantity'),
                *cls._columns(quantities),
                where=(
                    (Coalesce(quantities.next_date, dt.date.max) >= from_date)
                    | (quantities.date >= from_date))))

    @classmethod
    def _quantities_columns(cls, move, product):
        yield from []

    @classmethod
    def _quantities_group_by(cls, move, product):
        yield from []

    @classmethod
    def _quantities_order_by(cls, quantities):
        yield quantities.date.asc

    @classmethod
    def _columns(cls, quantities):
        yield from []

    @classmethod
    def _where(cls, quantities):
        return Literal(True)

    @classmethod
    def _state_clause(cls, move, date):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        forcast = date > today

        move_date = Coalesce(move.effective_date, move.planned_date)
        state_clause = (
            (move_date <= today) & (move.state == 'done'))
        state_clause |= (
            ((move_date >= today) if forcast else (move_date > today))
            & (move.state.in_(['done', 'assigned', 'draft'])))
        return state_clause

    @fields.depends('product')
    def on_change_with_unit(self, name=None):
        if self.product:
            return self.product.default_uom


class InventoryContext(_InventoryContextMixin):
    __name__ = 'stock.reporting.inventory.context'

    date = fields.Date("Date", required=True)
    product_type = fields.Selection([
            ('product.product', "Variant"),
            ('product.template', "Product"),
            ], "Product Type", required=True)

    @classmethod
    def default_date(cls):
        return Pool().get('ir.date').today()

    @classmethod
    def default_product_type(cls):
        return Transaction().context.get('product_type') or 'product.template'


class Inventory(_InventoryMixin, ModelSQL, ModelView):
    __name__ = 'stock.reporting.inventory'


class _InventoryRangeContextMixin(_InventoryContextMixin):

    from_date = fields.Date(
        "From Date", required=True,
        domain=[
            ('from_date', '<=', Eval('to_date')),
            ])
    to_date = fields.Date(
        "To Date", required=True,
        domain=[
            ('to_date', '>=', Eval('from_date')),
            ])

    @classmethod
    def default_from_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        if 'from_date' in context:
            return context['from_date']
        return Date.today() - relativedelta(day=1, months=6)

    @classmethod
    def default_to_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        if 'to_date' in context:
            return context['to_date']
        return Date.today() + relativedelta(day=1, months=6)


class InventoryRangeContext(_InventoryRangeContextMixin):
    __name__ = 'stock.reporting.inventory.range.context'


class InventoryMove(_InventoryMixin, ModelSQL, ModelView):
    __name__ = 'stock.reporting.inventory.move'

    date = fields.Date("Date")
    move = fields.Many2One('stock.move', "Move")
    origin = fields.Reference("Origin", selection='get_origin')
    document = fields.Function(
        fields.Reference("Document", selection='get_documents'),
        'get_document')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('date', 'DESC'),
            ('move', 'DESC NULLS LAST'),
            ('id', 'DESC'),
            ]

    @classmethod
    def _quantities_columns(cls, move, product):
        from_date = Transaction().context.get('from_date') or dt.date.min
        move_date = Coalesce(move.effective_date, move.planned_date)
        yield from super()._quantities_columns(move, product)
        yield Case(
            (move_date < from_date, Null),
            else_=move.id).as_('move')
        yield Case(
            (move_date < from_date, Null),
            else_=move.origin).as_('origin')

    @classmethod
    def _quantities_order_by(cls, quantities):
        yield from super()._quantities_order_by(quantities)
        yield quantities.move.asc.nulls_first

    @classmethod
    def _quantities_group_by(cls, move, product):
        from_date = Transaction().context.get('from_date') or dt.date.min
        move_date = Coalesce(move.effective_date, move.planned_date)
        yield from super()._quantities_group_by(move, product)
        yield Case(
            (move_date < from_date, Null),
            else_=move.id)
        yield Case(
            (move_date < from_date, Null),
            else_=move.origin)

    @classmethod
    def _columns(cls, quantities):
        yield from super()._columns(quantities)
        yield quantities.date.as_('date')
        yield quantities.move.as_('move')
        yield quantities.origin.as_('origin')

    @classmethod
    def get_origin(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        return Move.get_origin()

    @classmethod
    def _get_document_models(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        return [m for m, _ in Move.get_shipment() if m]

    @classmethod
    def get_documents(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = cls._get_document_models()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    def get_document(self, name):
        if self.move and self.move.shipment:
            return str(self.move.shipment)

    def get_rec_name(self, name):
        name = super().get_rec_name(name)
        if self.move:
            name = self.move.rec_name
        return name


class InventoryDaily(_InventoryMixin, ModelSQL, ModelView):
    __name__ = 'stock.reporting.inventory.daily'

    from_date = fields.Date("From Date")
    to_date = fields.Date("To Date")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('from_date', 'DESC'),
            ('id', 'DESC'),
            ]

    @classmethod
    def _quantities_order_by(cls, quantities):
        yield from []
        yield quantities.date.asc

    @classmethod
    def _columns(cls, quantities):
        transaction = Transaction()
        context = transaction.context
        to_date = context.get('to_date') or dt.date.max

        yield from super()._columns(quantities)

        yield quantities.date.as_('from_date')
        yield Least(quantities.next_date, to_date).as_('to_date')


class InventoryTurnoverContext(_InventoryRangeContextMixin):
    __name__ = 'stock.reporting.inventory.turnover.context'

    product_type = fields.Selection([
            ('product.product', "Variant"),
            ('product.template', "Product"),
            ], "Product Type", required=True)

    @classmethod
    def default_product_type(cls):
        return Transaction().context.get('product_type') or 'product.template'


class InventoryTurnover(ModelSQL, ModelView):
    __name__ = 'stock.reporting.inventory.turnover'

    company = fields.Many2One('company.company', "Company")
    product = fields.Reference("Product", [
            ('product.product', "Variant"),
            ('product.template', "Product"),
            ])
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"),
        'on_change_with_unit')

    output_quantity = fields.Float("Output Quantity", digits=(None, 3))
    average_quantity = fields.Float("Average Quantity", digits=(None, 3))
    turnover = fields.Float("Turnover", digits=(None, 3))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Inventory = pool.get('stock.reporting.inventory.daily')

        transaction = Transaction()
        context = transaction.context
        inventory = Inventory.__table__()

        from_date = context.get('from_date') or dt.date.min
        to_date = context.get('to_date') or dt.date.max
        company = context.get('company')

        days = (to_date - from_date).days + 1

        output_quantity = Sum(inventory.output_quantity) / days
        inventory_from_date = inventory.from_date
        inventory_to_date = inventory.to_date
        if backend.name == 'sqlite':
            inventory_from_date = _SQLite_JulianDay(inventory_from_date)
            inventory_to_date = _SQLite_JulianDay(inventory_to_date)
        average_quantity = (
            Sum(Case(
                    (inventory.quantity >= 0, inventory.quantity),
                    else_=0)
                * (inventory_to_date - inventory_from_date
                    + Case((inventory.to_date == to_date, 1), else_=0)))
            / days)

        def round_sql(expression, digits=2):
            factor = 10 ** digits
            return Round(expression * factor) / factor

        return (inventory
            .select(
                cls.product.sql_id(inventory.product, cls).as_('id'),
                Literal(company).as_('company'),
                inventory.product.as_('product'),
                round_sql(
                    output_quantity,
                    cls.output_quantity.digits[1]).as_('output_quantity'),
                round_sql(
                    average_quantity,
                    cls.average_quantity.digits[1]).as_('average_quantity'),
                round_sql(
                    output_quantity / NullIf(average_quantity, 0),
                    cls.turnover.digits[1]).as_('turnover'),
                group_by=[inventory.product]))

    @fields.depends('product')
    def on_change_with_unit(self, name=None):
        if self.product:
            return self.product.default_uom
