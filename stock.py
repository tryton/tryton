# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal

from sql.operators import Concat
from sql.aggregate import Count

from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools import grouped_slice


__all__ = ['Configuration', 'ShipmentDrop', 'Move']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'stock.configuration'

    shipment_drop_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Drop Shipment Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.drop'),
                ], required=True))


class ShipmentDrop(Workflow, ModelSQL, ModelView):
    "Drop Shipment"
    __name__ = 'stock.shipment.drop'

    effective_date = fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date('Planned Date', states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'])
    reference = fields.Char('Reference', select=1,
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    supplier = fields.Many2One('party.party', 'Supplier', required=True,
        states={
            'readonly': (((Eval('state') != 'draft')
                    | Eval('supplier_moves', [0]))
                & Eval('supplier')),
            },
        depends=['state', 'supplier'])
    contact_address = fields.Many2One('party.address', 'Contact Address',
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[('party', '=', Eval('supplier'))],
        depends=['state', 'supplier'])
    customer = fields.Many2One('party.party', 'Customer', required=True,
        states={
            'readonly': (((Eval('state') != 'draft')
                    | Eval('customer_moves', [0]))
                & Eval('customer')),
            },
        depends=['state'])
    delivery_address = fields.Many2One('party.address', 'Delivery Address',
        required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[('party', '=', Eval('customer'))],
        depends=['state', 'customer'])
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
        depends=['company'], readonly=True)
    supplier_moves = fields.Function(fields.One2Many('stock.move', None,
            'Supplier Moves',
            states={
                'readonly': Eval('state').in_(['shipped', 'done', 'cancel']),
                },
            depends=['state', 'supplier']), 'get_moves', 'set_moves')
    customer_moves = fields.Function(fields.One2Many('stock.move', None,
            'Customer Moves',
            states={
                'readonly': Eval('state') != 'shipped',
                },
            depends=['state', 'customer']), 'get_moves', 'set_moves')
    code = fields.Char('Code', select=1, readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('shipped', 'Shipped'),
            ('done', 'Done'),
            ('cancel', 'Canceled'),
            ], 'State', readonly=True)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Move = pool.get('stock.move')
        PurchaseLine = pool.get('purchase.line')
        PurchaseRequest = pool.get('purchase.request')
        SaleLine = pool.get('sale.line')
        Location = pool.get('stock.location')
        move = Move.__table__()
        purchase_line = PurchaseLine.__table__()
        purchase_request = PurchaseRequest.__table__()
        sale_line = SaleLine.__table__()
        location = Location.__table__()
        cursor = Transaction().connection.cursor()

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

            create_move = move.insert(values=move.select(
                    where=move.shipment.like('stock.shipment.drop,%')))
            cursor.execute(*create_move)

            for move_id, customer_location, line_id in move_sales:
                cursor.execute(move.update(
                        columns=[move.origin, move.from_location,
                            move.to_location],
                        values=[Concat('sale.line,', str(line_id)),
                            drop_shipment_location, customer_location],
                        where=(move.id == move_id)))

    @classmethod
    def __setup__(cls):
        super(ShipmentDrop, cls).__setup__()
        cls.__rpc__.update({
                'button_draft': True,
                })
        cls._transitions |= set((
                ('draft', 'waiting'),
                ('waiting', 'shipped'),
                ('draft', 'cancel'),
                ('waiting', 'cancel'),
                ('waiting', 'draft'),
                ('cancel', 'draft'),
                ('shipped', 'done'),
                ('shipped', 'cancel'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state').in_(['cancel', 'done']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancel', 'draft',
                            'waiting']),
                    'icon': If(Eval('state') == 'cancel',
                        'tryton-clear', 'tryton-go-previous'),
                    },
                'wait': {
                    'invisible': Eval('state') != 'draft',
                    },
                'ship': {
                    'invisible': Eval('state') != 'waiting',
                    },
                'done': {
                    'invisible': Eval('state') != 'shipped',
                    },
                })
        cls._error_messages.update({
                'reset_move': ('You cannot reset to draft move "%s" which was '
                    'generated by a sale or a purchase.'),
                })

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
        for shipment in shipments:
            planned_date = shipment._get_move_planned_date()
            Move.write([m for m in shipment.moves
                    if m.state not in ('assigned', 'done', 'cancel')], {
                    'planned_date': planned_date,
                    })

    def get_moves(self, name):
        if name == 'supplier_moves':
            return [m.id for m in self.moves if m.to_location.type == 'drop']
        elif name == 'customer_moves':
            return [m.id for m in self.moves if m.from_location.type == 'drop']

    @classmethod
    def set_moves(cls, shipments, name, values):
        if not values:
            return
        cls.write(shipments, {'moves': values})

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            values['code'] = Sequence.get_id(config.shipment_drop_sequence)
        shipments = super(ShipmentDrop, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        PurchaseLine = pool.get('purchase.line')
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        super(ShipmentDrop, cls).write(*args)
        cls._set_move_planned_date(sum(args[::2], []))

        actions = iter(args)
        for shipments, values in zip(actions, actions):
            if values.get('state', '') not in ('done', 'cancel'):
                continue
            with Transaction().set_context(_check_access=False):
                move_ids = [m.id for s in shipments for m in s.customer_moves]
                sale_lines = []
                for sub_moves in grouped_slice(move_ids):
                    sale_lines += SaleLine.search([
                            ('moves', 'in', list(sub_moves)),
                            ])
                sales = list(set(l.sale for l in sale_lines or []))
                Sale.process(sales)

                move_ids = [m.id for s in shipments for m in s.supplier_moves]
                purchase_lines = []
                for sub_moves in grouped_slice(move_ids):
                    purchase_lines += PurchaseLine.search([
                            ('moves', 'in', move_ids),
                            ])
                purchases = list(set(l.purchase for l in purchase_lines or []))
                Purchase.process(purchases)

    @classmethod
    def copy(cls, shipments, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = None
        return super(ShipmentDrop, cls).copy(shipments, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, shipments):
        Move = Pool().get('stock.move')
        Move.cancel([m for s in shipments for m in s.supplier_moves])
        Move.write([m for s in shipments for m in s.customer_moves],
            {'shipment': None})

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
                if (move.state == 'cancel'
                        and isinstance(move.origin, (PurchaseLine, SaleLine))):
                    cls.raise_user_error('reset_move', (move.rec_name,))
        Move.draft([m for s in shipments for m in s.moves
                if m.state != 'staging'])

    @classmethod
    def _synchronize_moves(cls, shipments):
        pool = Pool()
        UoM = pool.get('product.uom')
        Move = pool.get('stock.move')

        to_save = []
        cost_exp = Decimal(str(10.0 ** -Move.cost_price.digits[1]))
        for shipment in shipments:
            product_qty = defaultdict(lambda: 0)
            product_cost = defaultdict(lambda: 0)
            for s_move in shipment.supplier_moves:
                if s_move.state == 'cancel':
                    continue
                product_qty[s_move.product] += UoM.compute_qty(s_move.uom,
                    s_move.quantity, s_move.product.default_uom, round=False)
                if s_move.cost_price:
                    internal_quantity = Decimal(str(s_move.internal_quantity))
                    product_cost[s_move.product] += (
                        s_move.unit_price * internal_quantity)
            for product, cost in product_cost.iteritems():
                qty = Decimal(str(product_qty[product]))
                product_cost[product] = (cost / qty).quantize(cost_exp)
            for c_move in shipment.customer_moves:
                if c_move.state == 'cancel':
                    continue
                if product_qty[c_move.product] <= 0:
                    c_move.shipment = None
                else:
                    move_qty = UoM.compute_qty(c_move.uom, c_move.quantity,
                        c_move.product.default_uom, round=False)
                    qty = min(product_qty[c_move.product], move_qty)
                    c_move.quantity = UoM.compute_qty(
                        c_move.product.default_uom,
                        qty, c_move.uom)
                    product_qty[c_move.product] -= qty
                    c_move.cost_price = product_cost[c_move.product]
                to_save.append(c_move)
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
                    for m in s.supplier_moves]):
            requests += PurchaseRequest.search([
                    ('purchase_line', 'in', list(sub_lines)),
                    ])
        pline2request = {r.purchase_line: r for r in requests}
        sale_lines = SaleLine.search([
                ('purchase_request', 'in', [r.id for r in requests]),
                ])
        request2sline = {sl.purchase_request: sl for sl in sale_lines}

        to_save = []
        for shipment in shipments:
            for move in shipment.supplier_moves:
                sale_line = request2sline[pline2request[move.origin]]
                for move in sale_line.moves:
                    if (move.state not in ('cancel', 'done')
                            and not move.shipment
                            and move.from_location.type == 'drop'):
                        move.shipment = shipment
                        to_save.append(move)
        Move.save(to_save)
        cls._synchronize_moves(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('shipped')
    def ship(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Move.do([m for s in shipments for m in s.supplier_moves])
        cls._synchronize_moves(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        Move.do([m for s in shipments for m in s.customer_moves])
        cls.write(shipments, {
                'effective_date': Date.today(),
                })


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'stock.move'

    customer_drop = fields.Function(fields.Many2One('party.party',
            'Drop Customer'), 'get_customer_drop',
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
            return self.origin.purchase.customer.id

    @classmethod
    def search_customer_drop(cls, name, clause):
        return ['OR',
            ('origin.sale.party',) + tuple(clause[1:]) + ('sale.line',),
            (('origin.purchase.customer',) + tuple(clause[1:])
                + ('purchase.line',)),
            ]
