# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal
from itertools import groupby

from sql import Column
from sql.aggregate import Count
from sql.conditionals import Coalesce
from sql.functions import CharLength
from sql.operators import Concat

from trytond import backend
from trytond.i18n import gettext
from trytond.model import Index, ModelSQL, ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.modules.product import round_price
from trytond.modules.purchase.stock import process_purchase
from trytond.modules.sale.stock import process_sale
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id, If
from trytond.tools import cursor_dict, grouped_slice
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
        return super(Configuration, cls).multivalue_model(field)

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
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)
        if exist:
            table = cls.__table_handler__(module_name)
            exist &= table.column_exist('shipment_drop_sequence')

        super(ConfigurationSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('shipment_drop_sequence')
        value_names.append('shipment_drop_sequence')
        super(ConfigurationSequence, cls)._migrate_property(
            field_names, value_names, fields)

    @classmethod
    def default_shipment_drop_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'sale_supply_drop_shipment', 'sequence_shipment_drop')
        except KeyError:
            return None


class ShipmentDrop(Workflow, ModelSQL, ModelView):
    "Drop Shipment"
    __name__ = 'stock.shipment.drop'
    _rec_name = 'number'
    effective_date = fields.Date(
        "Effective Date",
        states={
            'readonly': Eval('state').in_(['cancelled', 'done']),
            },
        help="When the stock was actually sent.")
    planned_date = fields.Date('Planned Date', states={
            'readonly': Eval('state') != 'draft',
            })
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    reference = fields.Char(
        "Reference",
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
        domain=[('party', '=', Eval('supplier'))])
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
        domain=[('party', '=', Eval('customer'))])
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
        domain=[
            ('company', '=', Eval('company')),
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
    number = fields.Char(
        "Number", readonly=True,
        help="The main identifier for the shipment.")
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('shipped', 'Shipped'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ], "State", readonly=True, sort=False)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Move = pool.get('stock.move')
        PurchaseLine = pool.get('purchase.line')
        PurchaseRequest = pool.get('purchase.request')
        SaleLine = pool.get('sale.line')
        Location = pool.get('stock.location')
        table = cls.__table__()
        move = Move.__table__()
        purchase_line = PurchaseLine.__table__()
        purchase_request = PurchaseRequest.__table__()
        sale_line = SaleLine.__table__()
        location = Location.__table__()
        cursor = Transaction().connection.cursor()

        table_h = cls.__table_handler__(module_name)
        # Migration from 5.8: rename code into number
        if table_h.column_exist('code'):
            table_h.column_rename('code', 'number')

        super(ShipmentDrop, cls).__register__(module_name)

        # Migration from 3.6
        cursor.execute(*location.select(Count(location.id),
                where=(location.type == 'drop')))
        has_drop_shipment, = cursor.fetchone()

        if not has_drop_shipment:
            drop_shipment = Location(name='Migration Drop Shipment',
                type='drop', active=False)
            drop_shipment.save()
            drop_shipment_location = drop_shipment.id

            move_sale_query = move.join(purchase_line,
                condition=move.origin == Concat('purchase.line,',
                    purchase_line.id)
                ).join(purchase_request,
                condition=purchase_request.purchase_line == purchase_line.id
                ).join(sale_line,
                condition=sale_line.purchase_request == purchase_request.id
                ).select(
                    move.id, move.to_location, sale_line.id,
                    where=move.shipment.like('stock.shipment.drop,%'))
            cursor.execute(*move_sale_query)
            move_sales = cursor.fetchall()

            for sub_move in grouped_slice(move_sales):
                sub_ids = [s[0] for s in sub_move]
                cursor.execute(*move.update(
                        columns=[move.to_location],
                        values=[drop_shipment_location],
                        where=move.id.in_(sub_ids)))

            cursor.execute(*move.select(limit=1))
            moves = list(cursor_dict(cursor))
            if moves:
                move_columns = moves[0].keys()
                columns = [Column(move, c) for c in move_columns if c != 'id']
                create_move = move.insert(
                    columns=columns, values=move.select(
                        *columns,
                        where=move.shipment.like('stock.shipment.drop,%')))
                cursor.execute(*create_move)

            for move_id, customer_location, line_id in move_sales:
                cursor.execute(*move.update(
                        columns=[move.origin, move.from_location,
                            move.to_location],
                        values=[Concat('sale.line,', str(line_id)),
                            drop_shipment_location, customer_location],
                        where=(move.id == move_id)))

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*table.update(
                [table.state], ['cancelled'],
                where=table.state == 'cancel'))

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super(ShipmentDrop, cls).__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.reference, Index.Similarity())),
                Index(
                    t, (t.state, Index.Equality()),
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
                ('cancelled', 'draft'),
                ('shipped', 'done'),
                ('shipped', 'cancelled'),
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
                'done': {
                    'invisible': Eval('state') != 'shipped',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

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
    def create(cls, vlist):
        pool = Pool()
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        default_company = cls.default_company()
        for values in vlist:
            values['number'] = config.get_multivalue(
                'shipment_drop_sequence',
                company=values.get('company', default_company)).get()
        shipments = super(ShipmentDrop, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, *args):
        super(ShipmentDrop, cls).write(*args)
        cls._set_move_planned_date(sum(args[::2], []))

    @classmethod
    def copy(cls, shipments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('moves', None)
        return super(ShipmentDrop, cls).copy(shipments, default=default)

    @classmethod
    def delete(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')

        cls.cancel(shipments)
        for shipment in shipments:
            if shipment.state != 'cancelled':
                raise AccessError(
                    gettext('sale_supply_drop_shipment'
                        '.msg_drop_shipment_delete_cancel') % {
                        'shipment': shipment.rec_name,
                        })
        Move.delete([m for s in shipments for m in s.supplier_moves])
        super(ShipmentDrop, cls).delete(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @process_sale('customer_moves')
    @process_purchase('supplier_moves')
    def cancel(cls, shipments):
        Move = Pool().get('stock.move')
        Move.cancel([m for s in shipments for m in s.supplier_moves])
        Move.cancel([m for s in shipments for m in s.customer_moves
                if s.state == 'shipped'])
        Move.write([m for s in shipments for m in s.customer_moves
                if s.state != 'shipped'], {
                'shipment': None,
                'origin_drop': None,
                })

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
                    move.uom, move.quantity,
                    move.product.default_uom, round=False)
                for customer_move in move.moves_drop:
                    customer_move = customer_moves.get(customer_move)
                    if customer_move.uom.category != move.uom.category:
                        continue
                    c_qty_default_uom = Uom.compute_qty(
                        customer_move.uom, customer_move.quantity,
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
                        move.product.default_uom, qty, move.uom)
                    if move.quantity != qty:
                        move.quantity = qty
                        moves.append(move)
        Move.save(moves)

    def _sync_move_key(self, move):
        return (
            ('product', move.product),
            ('uom', move.uom),
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
                    s_move.uom, s_move.quantity, s_move.product.default_uom,
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
        PurchaseRequest = pool.get('purchase.request')
        SaleLine = pool.get('sale.line')
        Move = pool.get('stock.move')

        requests = []
        for sub_lines in grouped_slice([m.origin.id for s in shipments
                    for m in s.supplier_moves if m.origin]):
            requests += PurchaseRequest.search([
                    ('purchase_line', 'in', list(sub_lines)),
                    ])
        pline2requests = defaultdict(list)
        for request in requests:
            pline2requests[request.purchase_line].append(request)
        sale_lines = []
        for sub_requests in grouped_slice([r.id for r in requests]):
            sale_lines += SaleLine.search([
                    ('purchase_request', 'in', list(sub_requests)),
                    ])
        request2slines = defaultdict(list)
        for sale_line in sale_lines:
            request2slines[sale_line.purchase_request].append(sale_line)

        to_save = []
        for shipment in shipments:
            for s_move in shipment.supplier_moves:
                if not s_move.origin:
                    continue
                for request in pline2requests[s_move.origin]:
                    for sale_line in request2slines[request]:
                        for c_move in sale_line.moves:
                            if (c_move.state not in ('cancelled', 'done')
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

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @process_sale('customer_moves')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        cls.set_cost(shipments)
        Move.delete([
                m for s in shipments for m in s.customer_moves
                if not m.quantity])
        Move.do([m for s in shipments for m in s.customer_moves])
        for company, shipments in groupby(shipments, key=lambda s: s.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([s for s in shipments if not s.effective_date], {
                    'effective_date': today,
                    })


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
            'invisible': ~Eval('drop_moves'),
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
        models = super(Move, cls)._get_shipment()
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
            ('origin.sale.party' + clause[0].lstrip(name),)
            + tuple(clause[1:3]) + ('sale.line',) + tuple(clause[3:]),
            ('origin.purchase.customer' + clause[0].lstrip(name),)
            + tuple(clause[1:3]) + ('purchase.line',) + tuple(clause[3:]),
            ]
