# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal

from sql import Column
from sql.operators import Concat
from sql.aggregate import Count

from trytond import backend
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools import grouped_slice, cursor_dict

from trytond.modules.sale.stock import process_sale
from trytond.modules.purchase.stock import process_purchase


__all__ = ['Configuration', 'ConfigurationSequence', 'ShipmentDrop', 'Move']


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    shipment_drop_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Drop Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.drop'),
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
            ('code', '=', 'stock.shipment.drop'),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)
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
    supplier_moves = fields.One2Many('stock.move', 'shipment',
        'Supplier Moves',
        filter=[('to_location.type', '=', 'drop')],
        states={
            'readonly': Eval('state').in_(['shipped', 'done', 'cancel']),
            },
        depends=['state', 'supplier'])
    customer_moves = fields.One2Many('stock.move', 'shipment',
        'Customer Moves',
        filter=[('from_location.type', '=', 'drop')],
        states={
            'readonly': Eval('state') != 'shipped',
            },
        depends=['state', 'customer'])
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

    @classmethod
    def __setup__(cls):
        super(ShipmentDrop, cls).__setup__()
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
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancel', 'draft',
                            'waiting']),
                    'icon': If(Eval('state') == 'cancel',
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
        cls._error_messages.update({
                'reset_move': ('You cannot reset to draft move "%s" which was '
                    'generated by a sale or a purchase.'),
                'delete_cancel': ('Drop Shipment "%(shipment)s" must be '
                    'cancelled before deletion.'),
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
        to_write = []
        for shipment in shipments:
            planned_date = shipment._get_move_planned_date()
            to_write.extend(([m for m in shipment.moves
                        if m.state not in ('assigned', 'done', 'cancel')], {
                        'planned_date': planned_date,
                        }))
        if to_write:
            Move.write(*to_write)

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
            if shipment.state != 'cancel':
                cls.raise_user_error('delete_cancel', {
                        'shipment': shipment.rec_name,
                        })
        Move.delete([m for s in shipments for m in s.supplier_moves])
        super(ShipmentDrop, cls).delete(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    @process_sale('customer_moves')
    @process_purchase('supplier_moves')
    def cancel(cls, shipments):
        Move = Pool().get('stock.move')
        Move.cancel([m for s in shipments for m in s.supplier_moves])
        Move.cancel([m for s in shipments for m in s.customer_moves
                if s.state == 'shipped'])
        Move.write([m for s in shipments for m in s.customer_moves
                if s.state != 'shipped'], {'shipment': None})

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
        Currency = pool.get('currency.currency')

        to_save = []
        cost_exp = Decimal(str(10.0 ** -Move.cost_price.digits[1]))
        for shipment in shipments:
            product_qty = defaultdict(lambda: 0)
            product_cost = defaultdict(lambda: 0)

            for c_move in shipment.customer_moves:
                if c_move.state == 'cancel':
                    continue
                product_qty[c_move.product] += UoM.compute_qty(
                    c_move.uom, c_move.quantity, c_move.product.default_uom,
                    round=False)

            s_product_qty = defaultdict(lambda: 0)
            for s_move in shipment.supplier_moves:
                if s_move.state == 'cancel':
                    continue
                internal_quantity = Decimal(str(s_move.internal_quantity))
                with Transaction().set_context(date=s_move.effective_date):
                    unit_price = Currency.compute(
                        s_move.currency, s_move.unit_price,
                        s_move.company.currency, round=False)
                unit_price = UoM.compute_price(
                    s_move.uom, unit_price, s_move.product.default_uom)
                product_cost[s_move.product] += (
                    unit_price * internal_quantity)

                quantity = UoM.compute_qty(
                    s_move.uom, s_move.quantity, s_move.product.default_uom,
                    round=False)
                s_product_qty[s_move.product] += quantity
                if product_qty[s_move.product]:
                    if quantity <= product_qty[s_move.product]:
                        product_qty[s_move.product] -= quantity
                        continue
                    else:
                        out_quantity = (
                            quantity - product_qty[s_move.product])
                        out_quantity = UoM.compute_qty(
                            s_move.product.default_uom, out_quantity,
                            s_move.uom)
                        product_qty[s_move.product] = 0
                else:
                    out_quantity = s_move.quantity

                if not out_quantity:
                    continue
                unit_price = UoM.compute_price(
                    s_move.product.default_uom, s_move.product.list_price,
                    s_move.uom)
                new_customer_move = shipment._get_customer_move(s_move)
                new_customer_move.quantity = out_quantity
                new_customer_move.unit_price = unit_price
                to_save.append(new_customer_move)

            for product, cost in product_cost.items():
                qty = Decimal(str(s_product_qty[product]))
                if qty:
                    product_cost[product] = (cost / qty).quantize(cost_exp)
            for c_move in list(shipment.customer_moves) + to_save:
                if c_move.id is not None and c_move.state == 'cancel':
                    continue
                c_move.cost_price = product_cost[c_move.product]
                if c_move.id is None:
                    continue
                if product_qty[c_move.product] > 0:
                    exc_qty = UoM.compute_qty(
                        c_move.product.default_uom,
                        product_qty[c_move.product], c_move.uom)
                    removed_qty = UoM.compute_qty(
                        c_move.uom, min(exc_qty, c_move.quantity),
                        c_move.product.default_uom, round=False)
                    c_move.quantity = max(
                        0, c_move.uom.round(c_move.quantity - exc_qty))
                    product_qty[c_move.product] -= removed_qty
                to_save.append(c_move)

        if to_save:
            Move.save(to_save)

    def _get_customer_move(self, move):
        pool = Pool()
        Move = pool.get('stock.move')
        return Move(
            from_location=move.to_location,
            to_location=self.customer.customer_location,
            product=move.product,
            uom=move.uom,
            quantity=move.quantity,
            shipment=self,
            planned_date=self.planned_date,
            company=move.company,
            currency=move.company.currency,
            unit_price=move.unit_price,
            )

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
        sale_lines = SaleLine.search([
                ('purchase_request', 'in', [r.id for r in requests]),
                ])
        request2slines = defaultdict(list)
        for sale_line in sale_lines:
            request2slines[sale_line.purchase_request].append(sale_line)

        to_save = []
        for shipment in shipments:
            for move in shipment.supplier_moves:
                if not move.origin:
                    continue
                for request in pline2requests[move.origin]:
                    for sale_line in request2slines[request]:
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
        Move.do([m for s in shipments for m in s.customer_moves])
        cls.write(shipments, {
                'effective_date': Date.today(),
                })


class Move(metaclass=PoolMeta):
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
