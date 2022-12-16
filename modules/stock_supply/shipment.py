# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql import Table
from sql.functions import Overlay, Position

from trytond.model import ModelView, ModelSQL
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['ShipmentInternal',
    'CreateShipmentInternalStart', 'CreateShipmentInternal']


class ShipmentInternal(ModelSQL, ModelView):
    __name__ = 'stock.shipment.internal'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
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
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Date = pool.get('ir.date')
        User = pool.get('res.user')
        Move = pool.get('stock.move')
        LeadTime = pool.get('stock.location.lead_time')

        user_record = User(Transaction().user)
        today = Date.today()
        lead_time = LeadTime.get_max_lead_time()
        # fetch quantities on order points
        order_points = OrderPoint.search([
            ('type', '=', 'internal'),
            ])
        id2product = {}
        product2op = {}
        id2location = {}
        for op in order_points:
            id2product[op.product.id] = op.product
            product2op[
                (op.storage_location.id, op.product.id)
                ] = op
            id2location[op.storage_location.id] = op.storage_location
        provisioned = Location.search([
                ('provisioning_location', '!=', None),
                ])
        id2location.update({l.id: l for l in provisioned})
        location_ids = id2location.keys()

        # ordered by ids to speedup reduce_ids in products_by_location
        if provisioned:
            products = Product.search([
                    ('type', 'in', ['goods', 'assets']),
                    ], order=[('id', 'ASC')])
            product_ids = [p.id for p in products]
        else:
            product_ids = id2product.keys()
            product_ids.sort()

        with Transaction().set_context(forecast=True, stock_date_end=today):
            pbl = Product.products_by_location(
                location_ids, product_ids, with_childs=True)

        shipments = []
        date = today
        end_date = date + lead_time
        current_qties = pbl.copy()
        while date <= end_date:
            # Create a list of moves to create
            moves = {}
            for location in id2location.itervalues():
                for product_id in product_ids:
                    qty = current_qties.get((location.id, product_id), 0)
                    op = product2op.get((location.id, product_id))
                    if op:
                        min_qty, max_qty = op.min_quantity, op.max_quantity
                        prov_location = op.provisioning_location
                    elif location and location.provisioning_location:
                        min_qty, max_qty = 0, 0
                        prov_location = location.provisioning_location
                    else:
                        continue
                    if qty < min_qty:
                        key = (prov_location.id, location.id, product_id)
                        moves[key] = max_qty - qty
                        # Update quantities for move to create
                        current_qties[
                            (prov_location.id, product_id)] -= moves[key]
                        current_qties[(location.id, product_id)] += moves[key]

            # Group moves by {from,to}_location
            to_create = {}
            for key, qty in moves.iteritems():
                from_location, to_location, product = key
                to_create.setdefault(
                    (from_location, to_location), []).append((product, qty))
            # Create shipments and moves
            for locations, moves in to_create.iteritems():
                from_location, to_location = locations
                shipment = cls(
                    from_location=from_location,
                    to_location=to_location,
                    planned_date=date,
                    )
                shipment_moves = []
                for move in moves:
                    product_id, qty = move
                    product = id2product.setdefault(
                        product_id, Product(product_id))
                    shipment_moves.append(Move(
                            from_location=from_location,
                            to_location=to_location,
                            planned_date=date,
                            product=product,
                            quantity=qty,
                            uom=product.default_uom,
                            company=user_record.company,
                            ))
                shipment.moves = shipment_moves
                shipment.planned_start_date = (
                    shipment.on_change_with_planned_start_date())
                shipments.append(shipment)
            date += datetime.timedelta(1)

            # Update quantities with next moves
            with Transaction().set_context(
                    forecast=True,
                    stock_date_start=date,
                    stock_date_end=date):
                pbl = Product.products_by_location(
                    location_ids, product_ids, with_childs=True)
            for key, qty in pbl.iteritems():
                current_qties[key] += qty

        cls.save(shipments)
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
