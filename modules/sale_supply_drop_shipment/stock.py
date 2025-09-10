# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal
from itertools import groupby

from sql.conditionals import Coalesce

from trytond.i18n import gettext
from trytond.model import Index, ModelSQL, ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.modules.product import round_price
from trytond.modules.purchase.stock import process_purchase
from trytond.modules.sale.stock import process_sale
from trytond.modules.stock.shipment import ShipmentCheckQuantity, ShipmentMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id, If
from trytond.transaction import Transaction


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    shipment_drop_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Drop Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('sale_supply_drop_shipment',
                        'sequence_type_shipment_drop')),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'shipment_drop_sequence':
            return pool.get('stock.configuration.sequence')
        return super().multivalue_model(field)

    @classmethod
    def default_shipment_drop_sequence(cls, **pattern):
        return cls.multivalue_model(
            'shipment_drop_sequence').default_shipment_drop_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'stock.configuration.sequence'
    shipment_drop_sequence = fields.Many2One(
        'ir.sequence', "Drop Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('sale_supply_drop_shipment',
                    'sequence_type_shipment_drop')),
            ])

    @classmethod
    def default_shipment_drop_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'sale_supply_drop_shipment', 'sequence_shipment_drop')
        except KeyError:
            return None


class ShipmentDrop(
        ShipmentCheckQuantity, ShipmentMixin, Workflow, ModelSQL, ModelView):
    __name__ = 'stock.shipment.drop'

    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    supplier = fields.Many2One('party.party', 'Supplier', required=True,
        states={
            'readonly': (((Eval('state') != 'draft')
                    | Eval('supplier_moves', [0]))
                & Eval('supplier')),
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    contact_address = fields.Many2One('party.address', 'Contact Address',
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[('party', '=', Eval('supplier', -1))])
    customer = fields.Many2One('party.party', 'Customer', required=True,
        states={
            'readonly': (((Eval('state') != 'draft')
                    | Eval('customer_moves', [0]))
                & Eval('customer')),
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    delivery_address = fields.Many2One('party.address', 'Delivery Address',
        required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[('party', '=', Eval('customer', -1))])
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
        domain=[
            ('company', '=', Eval('company', -1)),
            ['OR',
                [
                    ('from_location.type', '=', 'supplier'),
                    ('to_location.type', '=', 'drop'),
                    ],
                [
                    ('from_location.type', '=', 'drop'),
                    ('to_location.type', '=', 'customer'),
                    ],
                ],
            ],
        readonly=True)
    supplier_moves = fields.One2Many('stock.move', 'shipment',
        'Supplier Moves',
        filter=[('to_location.type', '=', 'drop')],
        states={
            'readonly': Eval('state').in_(['shipped', 'done', 'cancelled']),
            },
        depends={'supplier'})
    customer_moves = fields.One2Many('stock.move', 'shipment',
        'Customer Moves',
        filter=[('from_location.type', '=', 'drop')],
        states={
            'readonly': Eval('state') != 'shipped',
            },
        depends={'customer'})
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('shipped', 'Shipped'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ], "State", readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(
                    t, (t.state, Index.Equality(cardinality='low')),
                    where=t.state.in_(['draft', 'waiting', 'shipped'])),
                })
        cls._order = [
            ('effective_date', 'ASC NULLS LAST'),
            ('id', 'DESC'),
            ]
        cls._transitions |= set((
                ('draft', 'waiting'),
                ('waiting', 'shipped'),
                ('draft', 'cancelled'),
                ('waiting', 'cancelled'),
                ('waiting', 'draft'),
                ('waiting', 'waiting'),
                ('cancelled', 'draft'),
                ('shipped', 'done'),
                ('shipped', 'cancelled'),
                ('done', 'cancelled'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state').in_(['cancelled', 'done']),
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancelled', 'draft',
                            'waiting']),
                    'icon': If(Eval('state') == 'cancelled',
                        'tryton-undo', 'tryton-back'),
                    'depends': ['state'],
                    },
                'wait': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'ship': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                'do': {
                    'invisible': Eval('state') != 'shipped',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def order_effective_date(cls, tables):
        table, _ = tables[None]
        return [Coalesce(table.effective_date, table.planned_date)]

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('supplier')
    def on_change_supplier(self):
        if self.supplier:
            self.contact_address = self.supplier.address_get()
        else:
            self.contact_address = None

    @fields.depends('customer')
    def on_change_customer(self):
        if self.customer:
            self.delivery_address = self.customer.address_get(type='delivery')
        else:
            self.delivery_address = None

    def _get_move_planned_date(self):
        '''
        Return the planned date for moves
        '''
        return self.planned_date

    @classmethod
    def _set_move_planned_date(cls, shipments):
        '''
        Set planned date of moves for the shipments
        '''
        Move = Pool().get('stock.move')
        to_write = []
        for shipment in shipments:
            planned_date = shipment._get_move_planned_date()
            to_write.extend(([m for m in shipment.moves
                        if m.state not in ('assigned', 'done', 'cancelled')
                        ], {
                        'planned_date': planned_date,
                        }))
        if to_write:
            Move.write(*to_write)

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('number'):
            company_id = values.get('company', cls.default_company())
            if company_id is not None:
                configuration = Configuration(1)
                if sequence := configuration.get_multivalue(
                        'shipment_drop_sequence', company=company_id):
                    values['number'] = sequence.get()
        return values

    @classmethod
    def copy(cls, shipments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('moves', None)
        default.setdefault('supplier_moves', None)
        default.setdefault('customer_moves', None)
        return super().copy(shipments, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @process_sale('customer_moves')
    @process_purchase('supplier_moves')
    def cancel(cls, shipments):
        Move = Pool().get('stock.move')
        Move.cancel([
                m for s in shipments
                for m in s.supplier_moves + s.customer_moves])

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        PurchaseLine = pool.get('purchase.line')
        SaleLine = pool.get('sale.line')
        for shipment in shipments:
            for move in shipment.moves:
                if (move.state == 'cancelled'
                        and isinstance(move.origin, (PurchaseLine, SaleLine))):
                    raise AccessError(
                        gettext('sale_supply_drop_shipment.msg_reset_move',
                            move=move.rec_name))
        Move.draft([m for s in shipments for m in s.moves
                if m.state != 'staging'])

    @classmethod
    def _synchronize_moves(cls, shipments):
        pool = Pool()
        Uom = pool.get('product.uom')
        Move = pool.get('stock.move')

        def active(move):
            return move.state != 'cancelled'

        moves = []
        for shipment in shipments:
            customer_moves = {m: m for m in shipment.customer_moves}
            supplier_qty = defaultdict(lambda: defaultdict(int))

            for move in filter(active, shipment.customer_moves):
                key = shipment._sync_move_key(move)
                supplier_qty[move][key] = 0
            for move in filter(active, shipment.supplier_moves):
                key = shipment._sync_move_key(move)
                qty_default_uom = Uom.compute_qty(
                    move.unit, move.quantity,
                    move.product.default_uom, round=False)
                for customer_move in move.moves_drop:
                    customer_move = customer_moves.get(customer_move)
                    if customer_move.unit.category != move.unit.category:
                        continue
                    c_qty_default_uom = Uom.compute_qty(
                        customer_move.unit, customer_move.quantity,
                        customer_move.product.default_uom, round=False)
                    qty = min(qty_default_uom, c_qty_default_uom)
                    supplier_qty[customer_move][key] += qty
                    qty_default_uom -= qty
                    if qty_default_uom <= 0:
                        break
                else:
                    supplier_qty[None][key] += qty_default_uom

            for customer_move in supplier_qty:
                if customer_move:
                    customer_key = shipment._sync_move_key(customer_move)
                for key, qty in supplier_qty[customer_move].items():
                    if customer_move and key == customer_key:
                        move = customer_move
                    else:
                        move = shipment._sync_customer_move(customer_move)
                        for name, value in key:
                            setattr(move, name, value)
                    qty = Uom.compute_qty(
                        move.product.default_uom, qty, move.unit)
                    if move.quantity != qty:
                        move.quantity = qty
                        moves.append(move)
        Move.save(moves)

    def _sync_move_key(self, move):
        return (
            ('product', move.product),
            ('unit', move.unit),
            )

    def _sync_customer_move(self, template=None):
        pool = Pool()
        Move = pool.get('stock.move')
        Purchase = pool.get('purchase.purchase')
        move = Move(
            from_location=Purchase.default_drop_location(),
            to_location=self.customer.customer_location,
            quantity=0,
            shipment=self,
            planned_date=self.planned_date,
            company=self.company,
            )
        if template:
            move.from_location = template.from_location
            move.to_location = template.to_location
            move.origin = template.origin
            move.origin_drop = template.origin_drop
        if move.on_change_with_unit_price_required():
            if template:
                move.unit_price = template.unit_price
                move.currency = template.currency
            else:
                move.unit_price = 0
                move.currency = self.company.currency
        else:
            move.unit_price = None
            move.currency = None
        return move

    @classmethod
    def set_cost(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        UoM = pool.get('product.uom')

        to_save = []
        for shipment in shipments:
            product_cost = defaultdict(int)
            s_product_qty = defaultdict(int)
            for s_move in shipment.supplier_moves:
                if s_move.state == 'cancelled':
                    continue
                internal_quantity = Decimal(str(s_move.internal_quantity))
                product_cost[s_move.product] += (
                    s_move.get_cost_price() * internal_quantity)

                quantity = UoM.compute_qty(
                    s_move.unit, s_move.quantity, s_move.product.default_uom,
                    round=False)
                s_product_qty[s_move.product] += quantity

            for product, cost in product_cost.items():
                qty = Decimal(str(s_product_qty[product]))
                if qty:
                    product_cost[product] = round_price(cost / qty)

            for move in shipment.moves:
                cost_price = product_cost[move.product]
                if cost_price != move.cost_price:
                    move.cost_price = cost_price
                    to_save.append(move)
        if to_save:
            Move.save(to_save)

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, shipments):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        Move = pool.get('stock.move')

        to_save = []
        for shipment in shipments:
            for s_move in shipment.supplier_moves:
                if not isinstance(s_move.origin, PurchaseLine):
                    continue
                p_line = s_move.origin
                for request in p_line.requests:
                    for sale_line in request.sale_lines:
                        for c_move in sale_line.moves:
                            if (c_move.state not in {'cancelled', 'done'}
                                    and not c_move.shipment
                                    and c_move.from_location.type == 'drop'):
                                c_move.shipment = shipment
                                c_move.origin_drop = s_move
                                to_save.append(c_move)
        Move.save(to_save)
        Move.draft(to_save)
        cls._synchronize_moves(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('shipped')
    @process_sale('customer_moves')
    @process_purchase('supplier_moves')
    def ship(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Move.do([m for s in shipments for m in s.supplier_moves])
        cls._synchronize_moves(shipments)
        to_assign, to_delete = [], []
        for shipment in shipments:
            for move in shipment.customer_moves:
                if move.quantity:
                    to_assign.append(move)
                else:
                    to_delete.append(move)
        Move.delete(to_delete)
        Move.assign(to_assign)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @process_sale('customer_moves')
    def do(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        cls.set_cost(shipments)
        customer_moves, to_delete = [], []
        for shipment in shipments:
            shipment.check_quantity()
            for move in shipment.customer_moves:
                if move.quantity:
                    customer_moves.append(move)
                else:
                    to_delete.append(move)
        Move.delete(to_delete)
        Move.do(customer_moves)
        for company, shipments in groupby(shipments, key=lambda s: s.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([s for s in shipments if not s.effective_date], {
                    'effective_date': today,
                    })

    @property
    def _check_quantity_source_moves(self):
        return self.supplier_moves

    @property
    def _check_quantity_target_moves(self):
        return self.customer_moves


class ShipmentDropSplit(metaclass=PoolMeta):
    __name__ = 'stock.shipment.drop'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'split_wizard': {
                    'readonly': Eval('state') != 'draft',
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    @classmethod
    @ModelView.button_action('stock_split.wizard_split_shipment')
    def split_wizard(cls, shipments):
        pass


class SplitShipment(metaclass=PoolMeta):
    __name__ = 'stock.shipment.split'

    def get_moves(self, shipment):
        moves = super().get_moves(shipment)
        if shipment.__name__ == 'stock.shipment.drop':
            moves = shipment.supplier_moves
        return moves

    def transition_split(self):
        shipment = self.record
        if shipment.__name__ == 'stock.shipment.drop':
            customer_moves = []
            for move in self.start.moves:
                customer_moves.extend(move.moves_drop)
            self.start.moves = [*self.start.moves, *customer_moves]
            self.start.domain_moves = [
                 *self.start.domain_moves, *customer_moves]
        return super().transition_split()


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    origin_drop = fields.Many2One(
        'stock.move', "Drop Origin", readonly=True,
        domain=[
            ('shipment', '=', Eval('shipment', -1)),
            ],
        states={
            'invisible': ~Eval('origin_drop'),
            })
    moves_drop = fields.One2Many(
        'stock.move', 'origin_drop', "Drop Moves", readonly=True,
        states={
            'invisible': ~Eval('moves_drop'),
            })
    customer_drop = fields.Function(fields.Many2One(
            'party.party', "Drop Customer",
            context={
                'company': Eval('company', -1),
                },
            depends={'company'}),
        'get_customer_drop',
        searcher='search_customer_drop')

    @classmethod
    def _get_shipment(cls):
        models = super()._get_shipment()
        models.append('stock.shipment.drop')
        return models

    def get_customer_drop(self, name):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        PurchaseLine = pool.get('purchase.line')

        if isinstance(self.origin, SaleLine):
            return self.origin.sale.party.id
        elif isinstance(self.origin, PurchaseLine):
            if self.origin.purchase.customer:
                return self.origin.purchase.customer.id

    @classmethod
    def search_customer_drop(cls, name, clause):
        return ['OR',
            ('origin.sale.party' + clause[0][len(name):],
                *clause[1:3], 'sale.line', *clause[3:]),
            ('origin.purchase.customer' + clause[0][len(name):],
                *clause[1:3], 'purchase.line', *clause[3:]),
            ]

    @classmethod
    def copy(cls, moves, default=None):
        context = Transaction().context
        if (context.get('_stock_move_split')
                and not context.get('_stock_move_split_drop')):
            for move in moves:
                if move.moves_drop:
                    raise AccessError(
                        gettext('sale_supply_drop_shipment'
                            '.msg_move_split_drop'))
        default = default.copy() if default is not None else {}
        default.setdefault('moves_drop')
        return super().copy(moves, default=default)


class MoveSplit(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def split(self, quantity, unit, count=None):
        with Transaction().set_context(_stock_move_split_drop=True):
            moves = super().split(quantity, unit, count=count)
        if self.moves_drop:
            to_save = []
            moves_drop = list(self.moves_drop)
            for move in moves:
                remainder = move.quantity
                while remainder > 0 and moves_drop:
                    move_drop = moves_drop.pop(0)
                    splits = move_drop.split(remainder, move.unit, count=1)
                    move_drop.origin_drop = move
                    remainder -= move_drop.quantity
                    to_save.append(move_drop)
                    splits.remove(move_drop)
                    moves_drop.extend(splits)
            self.__class__.save(to_save)
        return moves
