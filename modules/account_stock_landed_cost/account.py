# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from itertools import groupby
from operator import itemgetter

from sql.functions import CharLength

from trytond import backend
from trytond.i18n import gettext
from trytond.model import (
    Index, MatchMixin, ModelSQL, ModelView, Workflow, fields)
from trytond.modules.company.model import CompanyValueMixin
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id
from trytond.tools.multivalue import migrate_property
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

from .exceptions import FilterUnusedWarning, NoMoveWarning


def _parents(records):
    for record in records:
        while record:
            yield record
            record = record.parent


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    landed_cost_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Landed Cost Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('account_stock_landed_cost',
                        'sequence_type_landed_cost')),
                ]))

    @classmethod
    def default_landed_cost_sequence(cls, **pattern):
        return cls.multivalue_model(
            'landed_cost_sequence').default_landed_cost_sequence()


class ConfigurationLandedCostSequence(ModelSQL, CompanyValueMixin):
    "Account Configuration Landed Cost Sequence"
    __name__ = 'account.configuration.landed_cost_sequence'
    landed_cost_sequence = fields.Many2One(
        'ir.sequence', "Landed Cost Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('account_stock_landed_cost', 'sequence_type_landed_cost')),
            ])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(ConfigurationLandedCostSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('landed_cost_sequence')
        value_names.append('landed_cost_sequence')
        fields.append('company')
        migrate_property(
            'account.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_landed_cost_sequence(cls, **pattern):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'account_stock_landed_cost', 'sequence_landed_cost')
        except KeyError:
            return None


class LandedCost(Workflow, ModelSQL, ModelView, MatchMixin):
    'Landed Cost'
    __name__ = 'account.landed_cost'
    _rec_name = 'number'
    number = fields.Char("Number", readonly=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    shipments = fields.Many2Many('account.landed_cost-stock.shipment.in',
        'landed_cost', 'shipment', 'Shipments',
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('company', '=', Eval('company')),
            ('state', 'in', ['received', 'done']),
            ])
    invoice_lines = fields.One2Many('account.invoice.line', 'landed_cost',
        'Invoice Lines',
        states={
            'readonly': Eval('state') != 'draft',
            },
        add_remove=[
            ('landed_cost', '=', None),
            ],
        domain=[
            ('company', '=', Eval('company', -1)),
            ('invoice.state', 'in', ['posted', 'paid']),
            ('invoice.type', '=', 'in'),
            ('product.landed_cost', '=', True),
            ('type', '=', 'line'),
            ])
    allocation_method = fields.Selection([
            ('value', 'By Value'),
            ], 'Allocation Method', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })

    categories = fields.Many2Many(
        'account.landed_cost-product.category', 'landed_cost', 'category',
        "Categories",
        states={
            'readonly': Eval('state') != 'draft',
            },
        help="Apply only to products of these categories.")
    products = fields.Many2Many(
        'account.landed_cost-product.product', 'landed_cost', 'product',
        "Products",
        states={
            'readonly': Eval('state') != 'draft',
            },
        help="Apply only to these products.")

    posted_date = fields.Date('Posted Date', readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('cancelled', 'Cancelled'),
            ], "State", readonly=True, sort=False)

    factors = fields.Dict(None, "Factors", readonly=True)

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        super(LandedCost, cls).__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(
            Index(t, (t.state, Index.Equality()), where=t.state == 'draft'))
        cls._order = [
            ('number', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._transitions |= set((
                ('draft', 'posted'),
                ('draft', 'cancelled'),
                ('posted', 'cancelled'),
                ('cancelled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') == 'cancelled',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state') != 'cancelled',
                    'depends': ['state'],
                    },
                'post_wizard': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'show': {
                    'invisible': Eval('state').in_(['draft', 'cancelled']),
                    'depends': ['state']
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table_h = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        # Migration from 3.8: rename code into number
        if table_h.column_exist('code'):
            table_h.column_rename('code', 'number')

        super(LandedCost, cls).__register__(module_name)

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'cancel'))

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_allocation_method():
        return 'value'

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, landed_costs):
        for landed_cost in landed_costs:
            if landed_cost.state == 'posted':
                getattr(landed_cost, 'unallocate_cost_by_%s' %
                    landed_cost.allocation_method)()
        cls.write(landed_costs, {
                'posted_date': None,
                'factors': None,
                'state': 'cancelled',
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, landed_costs):
        pass

    @property
    def cost(self):
        pool = Pool()
        Currency = pool.get('currency.currency')

        currency = self.company.currency
        cost = Decimal(0)

        for line in self.invoice_lines:
            with Transaction().set_context(date=line.invoice.currency_date):
                cost += Currency.compute(
                    line.invoice.currency, line.amount, currency, round=False)
        return cost

    def stock_moves(self):
        moves = []
        for shipment in self.shipments:
            for move in shipment.incoming_moves:
                if move.state == 'cancelled':
                    continue
                if self._stock_move_filter(move):
                    moves.append(move)
        return moves

    def _stock_move_filter(self, move):
        if not self.categories and not self.products:
            return True
        result = False
        if self.categories:
            result |= bool(
                set(self.categories)
                & set(_parents(move.product.categories_all)))
        if self.products:
            result |= bool(move.product in self.products)
        return result

    def _stock_move_filter_unused(self, moves):
        pool = Pool()
        Warning = pool.get('res.user.warning')

        categories = {
            c for m in moves for c in _parents(m.product.categories_all)}
        for category in self.categories:
            if category not in categories:
                key = '%s - %s' % (self, category)
                if Warning.check(key):
                    raise FilterUnusedWarning(
                        key,
                        gettext('account_stock_landed_cost'
                            '.msg_landed_cost_unused_category',
                            landed_cost=self.rec_name,
                            category=category.rec_name))

        products = {m.product for m in moves}
        for product in self.products:
            if product not in products:
                key = '%s - %s' % (self, product)
                if Warning.check(key):
                    raise FilterUnusedWarning(
                        key,
                        gettext('account_stock_landed_cost'
                            '.msg_landed_cost_unused_product',
                            landed_cost=self.rec_name,
                            product=product.rec_name))

    def allocate_cost_by_value(self):
        self.factors = self._get_factors('value')
        self._allocate_cost(self.factors)

    def unallocate_cost_by_value(self):
        factors = self.factors or self._get_factors('value')
        self._allocate_cost(factors, sign=-1)

    def _get_factors(self, method=None):
        if method is None:
            method = self.allocation_method
        return getattr(self, '_get_%s_factors' % method)()

    def _get_value_factors(self):
        "Return the factor for each move based on value"
        pool = Pool()
        Currency = pool.get('currency.currency')

        currency = self.company.currency
        moves = self.stock_moves()

        sum_value = 0
        unit_prices = {}
        for move in moves:
            with Transaction().set_context(date=move.effective_date):
                unit_price = Currency.compute(
                    move.currency, move.unit_price, currency, round=False)
            unit_prices[move.id] = unit_price
            sum_value += unit_price * Decimal(str(move.quantity))

        factors = {}
        length = Decimal(len(moves))
        for move in moves:
            quantity = Decimal(str(move.quantity))
            if not sum_value:
                factors[str(move.id)] = 1 / length
            else:
                factors[str(move.id)] = (
                    quantity * unit_prices[move.id] / sum_value)
        return factors

    def _costs_to_allocate(self, moves, factors):
        pool = Pool()
        Move = pool.get('stock.move')
        cost = self.cost
        costs = []
        digit = Move.unit_price.digits[1]
        exp = Decimal(str(10.0 ** -digit))
        difference = cost
        for move in moves:
            quantity = Decimal(str(move.quantity))
            move_cost = cost * factors[str(move.id)]
            unit_landed_cost = round_price(
                move_cost / quantity, rounding=ROUND_DOWN)
            costs.append({
                    'unit_landed_cost': unit_landed_cost,
                    'difference': move_cost - (unit_landed_cost * quantity),
                    'move': move,
                    })
            difference -= unit_landed_cost * quantity
        costs.sort(key=itemgetter('difference'), reverse=True)
        for cost in costs:
            move = cost['move']
            quantity = Decimal(str(move.quantity))
            if exp * quantity <= difference:
                cost['unit_landed_cost'] += exp
                difference -= exp * quantity
            if difference < exp:
                break
        return costs

    def _allocate_cost(self, factors, sign=1):
        "Allocate cost on moves using factors"
        pool = Pool()
        Move = pool.get('stock.move')
        Currency = pool.get('currency.currency')
        assert sign in {1, -1}

        currency = self.company.currency
        moves = [m for m in self.stock_moves() if m.quantity]
        costs = self._costs_to_allocate(moves, factors)

        for cost in costs:
            move = cost['move']
            with Transaction().set_context(date=move.effective_date):
                unit_landed_cost = Currency.compute(
                    currency, cost['unit_landed_cost'],
                    move.currency, round=False)
            unit_landed_cost = round_price(
                unit_landed_cost, rounding=ROUND_HALF_EVEN)
            if move.unit_landed_cost is None:
                move.unit_landed_cost = 0
            move.unit_price += unit_landed_cost * sign
            move.unit_landed_cost += unit_landed_cost * sign
        Move.save(moves)

    @classmethod
    @ModelView.button_action(
        'account_stock_landed_cost.wizard_landed_cost_post')
    def post_wizard(cls, landed_costs):
        pass

    @classmethod
    @ModelView.button_action(
        'account_stock_landed_cost.wizard_landed_cost_show')
    def show(cls, landed_costs):
        pass

    @classmethod
    @Workflow.transition('posted')
    def post(cls, landed_costs):
        pool = Pool()
        Date = pool.get('ir.date')
        Warning = pool.get('res.user.warning')
        today = Date.today()

        for landed_cost in landed_costs:
            stock_moves = landed_cost.stock_moves()
            if not stock_moves:
                key = '%s post no move' % landed_cost
                if Warning.check(key):
                    raise NoMoveWarning(
                        key,
                        gettext('account_stock_landed_cost'
                            '.msg_landed_cost_post_no_stock_move',
                            landed_cost=landed_cost.rec_name))
            landed_cost._stock_move_filter_unused(stock_moves)
            getattr(landed_cost, 'allocate_cost_by_%s' %
                landed_cost.allocation_method)()
        for company, c_landed_costs in groupby(
                landed_costs, key=lambda l: l.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            for landed_cost in c_landed_costs:
                landed_cost.posted_date = today
            landed_cost.posted_date = today
        # Use save as allocate methods may modify the records
        cls.save(landed_costs)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Config = pool.get('account.configuration')

        vlist = [v.copy() for v in vlist]
        config = Config(1)
        default_company = cls.default_company()
        for values in vlist:
            if values.get('number') is None:
                values['number'] = config.get_multivalue(
                    'landed_cost_sequence',
                    company=values.get('company', default_company)).get()
        return super(LandedCost, cls).create(vlist)

    @classmethod
    def copy(cls, landed_costs, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('invoice_lines', None)
        return super().copy(landed_costs, default=default)


class LandedCost_Shipment(ModelSQL):
    'Landed Cost - Shipment'
    __name__ = 'account.landed_cost-stock.shipment.in'
    landed_cost = fields.Many2One(
        'account.landed_cost', 'Landed Cost',
        required=True, ondelete='CASCADE')
    shipment = fields.Many2One(
        'stock.shipment.in', 'Shipment', required=True, ondelete='CASCADE')


class LandedCost_ProductCategory(ModelSQL):
    "Landed Cost - Product Category"
    __name__ = 'account.landed_cost-product.category'
    landed_cost = fields.Many2One(
        'account.landed_cost', 'Landed Cost',
        required=True, ondelete='CASCADE')
    category = fields.Many2One(
        'product.category', "Category", required=True, ondelete='CASCADE')


class LandedCost_Product(ModelSQL):
    "Landed Cost - Product"
    __name__ = 'account.landed_cost-product.product'
    landed_cost = fields.Many2One(
        'account.landed_cost', "Landed Cost",
        required=True, ondelete='CASCADE')
    product = fields.Many2One(
        'product.product', "Product", required=True, ondelete='CASCADE')


class ShowLandedCostMixin(Wizard):
    start_state = 'show'
    show = StateView('account.landed_cost.show',
        'account_stock_landed_cost.landed_cost_show_view_form', [])

    @property
    def factors(self):
        return self.record._get_factors()

    def default_show(self, fields):
        moves = []
        default = {
            'cost': round_price(self.record.cost),
            'moves': moves,
            }
        stock_moves = [m for m in self.record.stock_moves() if m.quantity]
        costs = self.record._costs_to_allocate(stock_moves, self.factors)
        for cost in costs:
            moves.append({
                    'move': cost['move'].id,
                    'cost': round_price(
                        cost['unit_landed_cost'], rounding=ROUND_HALF_EVEN),
                    })
        return default


class PostLandedCost(ShowLandedCostMixin):
    "Post Landed Cost"
    __name__ = 'account.landed_cost.post'
    post = StateTransition()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.show.buttons.extend([
                Button("Cancel", 'end', 'tryton-cancel'),
                Button("Post", 'post', 'tryton-ok', default=True),
                ])

    def transition_post(self):
        self.model.post([self.record])
        return 'end'


class ShowLandedCost(ShowLandedCostMixin):
    "Show Landed Cost"
    __name__ = 'account.landed_cost.show'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.show.buttons.extend([
                Button("Close", 'end', 'tryton-close', default=True),
                ])

    @property
    def factors(self):
        return self.record.factors or super().factors


class LandedCostShow(ModelView):
    "Landed Cost Show"
    __name__ = 'account.landed_cost.show'

    cost = fields.Numeric("Cost", digits=price_digits, readonly=True)
    moves = fields.One2Many(
        'account.landed_cost.show.move', None, "Moves", readonly=True)


class LandedCostShowMove(ModelView):
    "Landed Cost Show"
    __name__ = 'account.landed_cost.show.move'

    move = fields.Many2One('stock.move', "Move", readonly=True)
    cost = fields.Numeric("Cost", digits=price_digits, readonly=True)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    landed_cost = fields.Many2One(
        'account.landed_cost', "Landed Cost", readonly=True,
        states={
            'invisible': ~Eval('landed_cost'),
            })

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls._check_modify_exclude.add('landed_cost')

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('landed_cost', None)
        return super(InvoiceLine, cls).copy(lines, default=default)
