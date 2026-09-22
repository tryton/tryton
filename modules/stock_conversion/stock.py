# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal
from itertools import groupby

from sql import Literal, Null
from sql.functions import CharLength
from sql.operators import Equal

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Exclude, ModelSQL, ModelView, Workflow, fields)
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import employee_field, set_employee
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id, If
from trytond.transaction import Transaction

from .exceptions import ConversionError


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    conversion_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Conversion Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('stock_conversion', 'sequence_type_conversion')),
                ],
            help="Used to generate the number given to conversion."))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'conversion_sequence':
            return pool.get('stock.configuration.sequence')
        return super().multivalue_model(field)

    @classmethod
    def default_conversion_sequence(cls, **pattern):
        return cls.multivalue_model(
            'conversion_sequence').default_conversion_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'stock.configuration.sequence'

    conversion_sequence = fields.Many2One(
        'ir.sequence', "Conversion Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('stock_conversion', 'sequence_type_conversion')),
            ])

    @classmethod
    def default_conversion_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock_conversion', 'sequence_conversion')
        except KeyError:
            return None


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    conversion_location = fields.Many2One(
        'stock.location', "Conversion",
        states={
            'invisible': Eval('type') != 'warehouse',
            'required': Eval('type') == 'warehouse',
            },
        domain=[
            ('type', '=', 'production'),
            ],
        help="Used to convert goods.")


class StockConversionRule(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'stock.conversion.rule'

    input_product = fields.Many2One(
        'product.product', "Input Product",
        required=True, ondelete='CASCADE',
        domain=[
            ('type', '=', 'goods'),
            ('id', '!=', Eval('output_product', -1)),
            ])
    input_quantity = fields.Float(
        "Input Quantity", digits='input_unit', required=True,
        domain=[
            ('input_quantity', '>', 0),
            ])
    input_unit = fields.Function(
        fields.Many2One('product.uom', "Input Unit"),
        'on_change_with_input_unit')
    output_product = fields.Many2One(
        'product.product', "Output Product",
        required=True, ondelete='RESTRICT',
        domain=[
            ('type', 'in', ['goods', 'assets']),
            ('id', '!=', Eval('input_product', -1)),
            ])
    output_quantity = fields.Float(
        "Output Quantity", digits='output_unit', required=True,
        domain=[
            ('output_quantity', '>', 0),
            ])
    output_unit = fields.Function(
        fields.Many2One('product.uom', "Output Unit"),
        'on_change_with_output_unit')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('input_output_unique',
                Exclude(t,
                    (t.input_product, Equal),
                    (t.output_product, Equal),
                    where=(t.active == Literal(True))),
                'stock_conversion.msg_conversion_rule_input_output_unique'),
            ]

    @classmethod
    def default_input_quantity(cls):
        return 1

    @classmethod
    def default_output_quantity(cls):
        return 1

    @fields.depends('input_product', '_parent_input_product.default_uom')
    def on_change_with_input_unit(self, name=None):
        return self.input_product.default_uom if self.input_product else None

    @fields.depends('output_product', '_parent_output_product.default_uom')
    def on_change_with_output_unit(self, name=None):
        return self.output_product.default_uom if self.output_product else None

    def get_rec_name(self, name):
        return (
            f"{self.input_product.rec_name} "
            "\N{black rightwards arrow} "
            f"{self.output_product.rec_name}")

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('input_product', operator, operand, *extra),
            ('output_product', operator, operand, *extra),
            ]

    @classmethod
    def check_modification(cls, mode, rules, values=None, external=False):
        pool = Pool()
        StockConversion = pool.get('stock.conversion')
        super().check_modification(
            mode, rules, values=values, external=external)
        if mode == 'write':
            if values.keys() & {
                    'input_product', 'input_quantity',
                    'output_product', 'output_quantity'}:
                conversions = StockConversion.search([
                        ('conversion_rule', 'in', [r.id for r in rules]),
                        ],
                    limit=1, order=[])
                if conversions:
                    raise AccessError(gettext(
                            'stock_conversion.'
                            'msg_conversion_rule_change_product_quantity'))

    def convert(self, quantity):
        return self.output_unit.floor(
            quantity * self.output_quantity / self.input_quantity)


class StockConversion(Workflow, ModelSQL, ModelView):
    __name__ = 'stock.conversion'
    _rec_name = 'number'

    number = fields.Char("Number", required=True, readonly=True)
    date = fields.Date("Date",
        states={
            'readonly': Eval('state') != 'draft',
            'required': Eval('state') == 'done',
            })
    company = fields.Many2One('company.company', "Company", required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            })
    location = fields.Many2One(
        'stock.location', "Location", required=True,
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('warehouse', -1)]),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            })

    input_product = fields.Many2One(
        'product.product', "Input Product", required=True,
        ondelete='CASCADE',
        domain=[
            If((Eval('state') == 'draft') & Eval('output_product', None),
                ('conversion_rules.output_product',
                    '=', Eval('output_product', -1)),
                ()),
            ('type', '=', 'goods'),
            ('id', '!=', Eval('output_product', -1)),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    input_unit = fields.Function(
        fields.Many2One('product.uom', "Input Unit"),
        'on_change_with_input_unit')
    input_quantity = fields.Float(
        "Input Quantity", digits='input_unit', required=True,
        domain=[
            ('input_quantity', '>', 0),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            })
    conversion_rule = fields.Many2One(
        'stock.conversion.rule', "Conversion Rule",
        required=True, ondelete='RESTRICT',
        domain=[
            If(Eval('input_product', None),
                ('input_product', '=', Eval('input_product', -1)),
                ()),
            If(Eval('output_product', None),
                ('output_product', '=', Eval('output_product', -1)),
                ()),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            })
    output_product = fields.Many2One(
        'product.product', "Output Product", required=True,
        domain=[
            If((Eval('state') == 'draft') & Eval('input_product', None),
                ('reverse_conversion_rules.input_product',
                    '=', Eval('input_product', -1)),
                ()),
            ('type', 'in', ['goods', 'assets']),
            ('id', '!=', Eval('input_product', -1)),
            ],
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    output_quantity = fields.Function(
        fields.Float("Output Quantity", digits='output_unit'),
        'on_change_with_output_quantity')
    output_unit = fields.Function(
        fields.Many2One('product.uom', "Output Unit"),
        'on_change_with_output_unit')

    moves = fields.One2Many(
        'stock.move', 'origin', "Moves", readonly=True,
        domain=['OR',
            [
                ('product', '=', Eval('input_product', -1)),
                ('from_location', '=', Eval('location', -1)),
                ('to_location.type', '=', 'production'),
                ],
            [
                ('product', '=', Eval('output_product', -1)),
                ('from_location.type', '=', 'production'),
                ('to_location', '=', Eval('location', -1)),
                ]
            ],
        states={
            'invisible': ~Eval('moves', None),
            })

    done_by = employee_field("Done By")
    state = fields.Selection([
            ('draft', 'Draft'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ], "State", readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        super().__setup__()
        cls._order = [
            ('date', 'DESC NULLS FIRST'),
            ('id', 'DESC'),
            ]
        cls._transitions |= set((
                ('draft', 'cancelled'),
                ('draft', 'done'),
                ('done', 'cancelled'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': (
                        (Eval('state') == 'cancelled')
                        | ((Eval('state') == 'done')
                            & ~Id('stock',
                                'group_stock_cancellation').in_(
                                Eval('context', {}).get('groups', []))
                            & ~Eval('context', {}).get(
                                'administrator', False))),
                    'depends': ['state'],
                    },
                'do': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [
            ~((table.state == 'cancelled') & (table.number == Null)),
            CharLength(table.number), table.number]

    @classmethod
    def default_date(cls):
        return Pool().get('ir.date').today()

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @fields.depends('input_product')
    def on_change_with_input_unit(self, name=None):
        if self.input_product:
            return self.input_product.default_uom

    @fields.depends('conversion_rule', 'input_quantity')
    def on_change_with_output_quantity(self, name=None):
        if self.input_quantity is not None and self.conversion_rule:
            return self.conversion_rule.convert(self.input_quantity)

    @fields.depends('output_product')
    def on_change_with_output_unit(self, name=None):
        if self.output_product:
            return self.output_product.default_uom

    @fields.depends(
        'input_product', 'output_product', 'conversion_rule',
        methods=['on_change_with_output_quantity'])
    def set_conversion_rule(self):
        pool = Pool()
        Rule = pool.get('stock.conversion.rule')
        if self.input_product and self.output_product:
            rule = self.conversion_rule
            if (not rule
                    or rule.input_product != self.input_product
                    or rule.output_product != self.output_product):
                try:
                    self.conversion_rule, = Rule.search([
                            ('input_product', '=', self.input_product),
                            ('output_product', '=', self.output_product),
                            ], limit=1)
                except ValueError:
                    pass
                self.output_quantity = self.on_change_with_output_quantity()

    @fields.depends(methods=['set_conversion_rule'])
    def on_change_input_product(self):
        self.set_conversion_rule()

    @fields.depends(methods=['set_conversion_rule'])
    def on_change_output_product(self):
        self.set_conversion_rule()

    @fields.depends('conversion_rule')
    def on_change_conversion_rule(self):
        if self.conversion_rule:
            self.input_product = self.conversion_rule.input_product
            self.output_product = self.conversion_rule.output_product

    @classmethod
    def default_state(cls):
        return 'draft'

    @property
    def input_moves(self):
        moves = []
        for move in self.moves:
            if move.from_location == self.location:
                moves.append(move)
        return moves

    @property
    def output_moves(self):
        moves = []
        for move in self.moves:
            if move.to_location == self.location:
                moves.append(move)
        return moves

    def _move(self, type):
        pool = Pool()
        Move = pool.get('stock.move')
        move = Move(**Move.default_get(with_rec_name=False))
        move.origin = self
        move.company = self.company
        move.effective_date = self.date
        if type == 'input':
            move.product = self.input_product
            move.unit = self.input_unit
            move.quantity = self.input_quantity
            move.from_location = self.location
            move.to_location = self.warehouse.conversion_location
        elif type == 'output':
            move.product = self.output_product
            move.unit = self.output_unit
            move.quantity = self.output_quantity
            move.from_location = self.warehouse.conversion_location
            move.to_location = self.location
            move.currency = self.company.currency
        else:
            raise ValueError(f"unsupported type {type}")
        move.unit_price_required = move.on_change_with_unit_price_required()
        if move.unit_price_required:
            if type == 'input':
                move.unit_price = move.product.cost_price
            elif type == 'output':
                cost_price = (
                    Decimal(str(self.input_quantity))
                    * self.input_product.cost_price)
                cost_price /= Decimal(str(self.output_quantity))
                move.unit_price = round_price(cost_price)
            if self.company:
                move.currency = self.company.currency
        else:
            move.unit_price = None
            move.currency = None
        return move

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        config = Configuration(1)
        values = super().preprocess_values(mode, values)
        if mode == 'create':
            if not values.get('number'):
                values['number'] = config.conversion_sequence.get()
        return values

    @classmethod
    def copy(cls, conversions, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('number')
        default.setdefault('done_by')
        default.setdefault('moves')
        return super().copy(conversions, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @set_employee('done_by')
    def do(cls, conversions):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('stock.move')
        Lang = pool.get('ir.lang')
        lang = Lang.get()

        for company, c_conversions in groupby(
                conversions, key=lambda c: c.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([c for c in c_conversions if not c.date], {
                    'date': today,
                    })

        moves = []
        for conversion in conversions:
            moves.append(conversion._move('input'))
            moves.append(conversion._move('output'))
        Move.save(moves)

        for conversion in conversions:
            if not Move.assign_try(conversion.input_moves, with_childs=False):
                quantity = sum(
                    m.quantity for m in conversion.input_moves
                    if m.state not in ['assigned', 'done', 'cancelled'])
                raise ConversionError(gettext(
                        'stock_conversion.msg_stock_conversion_missing_qty',
                        conversion=conversion.rec_name,
                        location=conversion.location.rec_name,
                        product=conversion.input_product.rec_name,
                        quantity=lang.format_number_symbol(
                            quantity, conversion.input_unit)))
        Move.do(moves)
        cls.set_cost(conversions)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, conversions):
        pool = Pool()
        Move = pool.get('stock.move')
        Move.cancel([m for c in conversions for m in c.moves])

    @property
    def cost(self):
        return round_price(sum(
                m.cost_price * Decimal(str(m.internal_quantity))
                for m in self.input_moves
                if m.cost_price and m.state != 'cancelled'))

    @classmethod
    def set_cost_from_moves(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        conversions = set()
        moves = Move.search([
                ('conversion_cost_price_updated', '=', True),
                ('origin', 'like', 'stock.conversion,%'),
                ],
            order=[('effective_date', 'ASC')])
        for move in moves:
            if move.origin not in conversions:
                cls.__queue__.set_cost([move.origin])
                conversions.add(move.origin)
        Move.write(moves, {'conversion_cost_price_updated': False})

    @classmethod
    def set_cost(cls, conversions):
        pool = Pool()
        Move = pool.get('stock.move')
        UoM = pool.get('product.uom')

        moves = []
        for conversion in conversions:
            cost = conversion.cost
            quantity = sum(
                m.internal_quantity for m in conversion.output_moves
                if m.state != 'cancelled'
                and m.product == conversion.output_product)
            if quantity:
                unit_price = cost / Decimal(str(quantity))
            else:
                unit_price = Decimal(0)
            for move in conversion.output_moves:
                if move.product == conversion.output_product:
                    m_unit_price = round_price(UoM.compute_price(
                            move.product.default_uom, unit_price, move.unit))
                else:
                    m_unit_price = Decimal(0)
                if (move.unit_price_required
                        and (move.unit_price != m_unit_price
                            or move.currency != conversion.company.currency)):
                    move.unit_price = m_unit_price
                    move.currency = conversion.company.currency
                    moves.append(move)
        Move.save(moves)


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    conversion_cost_price_updated = fields.Boolean(
        "Conversion Cost Price Updated", readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._allow_modify_closed_period.add('conversion_cost_price_updated')

    @classmethod
    def _get_origin(cls):
        return [*super()._get_origin(), 'stock.conversion']

    @classmethod
    def on_modification(cls, mode, moves, field_names=None):
        pool = Pool()
        Conversion = pool.get('stock.conversion')
        super().on_modification(mode, moves, field_names=field_names)
        if mode == 'write' and 'cost_price' in field_names:
            cls.write(
                [m for m in moves
                    if m.state == 'done'
                    and isinstance(m.origin, Conversion)],
                {'conversion_cost_price_updated': True})
