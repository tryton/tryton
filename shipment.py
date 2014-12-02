# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Table
from sql.functions import Overlay, Position

from trytond.model import ModelView, ModelSQL
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['ShipmentInternal',
    'CreateShipmentInternalStart', 'CreateShipmentInternal']
__metaclass__ = PoolMeta


class ShipmentInternal(ModelSQL, ModelView):
    __name__ = 'stock.shipment.internal'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        model_data = Table('ir_model_data')
        model = Table('ir_model')
        # Migration from 1.2: packing renamed into shipment
        cursor.execute(*model_data.update(
                columns=[model_data.fs_id],
                values=[Overlay(model_data.fs_id, 'shipment',
                        Position('packing', model_data.fs_id),
                        len('packing'))],
                where=model_data.fs_id.like('%packing%')
                & (model_data.module == module_name)))
        cursor.execute(*model.update(
                columns=[model.model],
                values=[Overlay(model.model, 'shipment',
                        Position('packing', model.model),
                        len('packing'))],
                where=model.model.like('%packing%')
                & (model.module == module_name)))
        super(ShipmentInternal, cls).__register__(module_name)

    @classmethod
    def generate_internal_shipment(cls):
        """
        Generate internal shipments to meet order points defined on
        non-warehouse location.
        """
        pool = Pool()
        OrderPoint = pool.get('stock.order_point')
        Product = pool.get('product.product')
        Date = pool.get('ir.date')
        User = pool.get('res.user')
        Move = pool.get('stock.move')
        user_record = User(Transaction().user)
        today = Date.today()
        # fetch quantities on order points
        order_points = OrderPoint.search([
            ('type', '=', 'internal'),
            ])
        id2product = {}
        location_ids = []
        for op in order_points:
            id2product[op.product.id] = op.product
            location_ids.append(op.storage_location.id)

        # TODO Allow to compute for other future date
        with Transaction().set_context(forecast=True, stock_date_end=today):
            pbl = Product.products_by_location(location_ids,
                list(id2product.iterkeys()), with_childs=True)

        # Create a list of move to create
        moves = {}
        for op in order_points:
            qty = pbl.get((op.storage_location.id, op.product.id), 0)
            if qty < op.min_quantity:
                key = (op.provisioning_location.id,
                       op.storage_location.id,
                       op.product.id)
                moves[key] = op.max_quantity - qty

        # Group moves by {from,to}_location
        to_create = {}
        for key, qty in moves.iteritems():
            from_location, to_location, product = key
            to_create.setdefault(
                (from_location, to_location), []).append((product, qty))
        # Create shipments and moves
        shipments = []
        for locations, moves in to_create.iteritems():
            from_location, to_location = locations
            shipment = cls(
                from_location=from_location,
                to_location=to_location,
                planned_date=today,
                )
            shipment_moves = []
            for move in moves:
                product, qty = move
                shipment_moves.append(Move(
                        from_location=from_location,
                        to_location=to_location,
                        product=product,
                        quantity=qty,
                        uom=id2product[product].default_uom,
                        company=user_record.company,
                        ))
            shipment.moves = shipment_moves
            shipment.save()
            shipments.append(shipment)
        cls.wait(shipments)
        return shipments


class CreateShipmentInternalStart(ModelView):
    'Create Shipment Internal'
    __name__ = 'stock.shipment.internal.create.start'


class CreateShipmentInternal(Wizard):
    'Create Shipment Internal'
    __name__ = 'stock.shipment.internal.create'
    start = StateView('stock.shipment.internal.create.start',
        'stock_supply.shipment_internal_create_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('stock.act_shipment_internal_form')

    def do_create_(self, action):
        ShipmentInternal = Pool().get('stock.shipment.internal')
        ShipmentInternal.generate_internal_shipment()
        return action, {}

    def transition_create_(self):
        return 'end'
