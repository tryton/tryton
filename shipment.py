#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['ShipmentInternal']
__metaclass__ = PoolMeta


class ShipmentInternal(ModelSQL, ModelView):
    __name__ = 'stock.shipment.internal'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model_data "
            "SET fs_id = REPLACE(fs_id, 'packing', 'shipment') "
            "WHERE fs_id like '%%packing%%' AND module = %s",
            (module_name,))
        cursor.execute("UPDATE ir_model "
            "SET model = REPLACE(model, 'packing', 'shipment') "
            "WHERE model like '%%packing%%' AND module = %s",
            (module_name,))
        super(ShipmentInternal, cls).__register__(module_name)

    @classmethod
    def generate_internal_shipment(cls):
        """
        Generate internal shipments to meet order points defined on
        non-warehouse location.
        """
        pool = Pool()
        OrderPoint = pool.get('stock.order_point')
        Uom = pool.get('product.uom')
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

        with Transaction().set_context(stock_date_end=today):
            pbl = Product.products_by_location(location_ids,
                list(id2product.iterkeys()), with_childs=True)

        # Create a list of move to create
        moves = {}
        for op in order_points:
            qty = pbl.get((op.storage_location.id, op.product.id), 0)
            if qty < op.min_quantity:
                key = (op.storage_location.id,
                       op.provisioning_location.id,
                       op.product.id)
                moves[key] = op.max_quantity - qty

        # Compare with existing draft shipments
        shipments = cls.search([
                ('state', '=', 'draft'),
                ['OR',
                    ('planned_date', '<=', today),
                    ('planned_date', '=', None),
                    ],
                ])
        for shipment in shipments:
            for move in shipment.moves:
                key = (shipment.to_location.id,
                       shipment.from_location.id,
                       move.product.id)
                if key not in moves:
                    continue
                quantity = Uom.compute_qty(move.uom, move.quantity,
                    id2product[move.product.id].default_uom)
                moves[key] = max(0, moves[key] - quantity)

        # Group moves by {from,to}_location
        shipments = {}
        for key, qty in moves.iteritems():
            from_location, to_location, product = key
            shipments.setdefault(
                (from_location, to_location), []).append((product, qty))
        # Create shipments and moves
        for locations, moves in shipments.iteritems():
            from_location, to_location = locations
            shipment = cls(
                from_location=from_location,
                to_location=to_location,
                planned_date=today,
                moves=[],
                )
            for move in moves:
                product, qty = move
                shipment.moves.append(Move(
                        from_location=from_location,
                        to_location=to_location,
                        product=product,
                        quantity=qty,
                        uom=id2product[product].default_uom,
                        company=user_record.company,
                        ))
            shipment.save()
