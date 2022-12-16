#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL


class ShipmentInternal(ModelSQL, ModelView):
    _name = 'stock.shipment.internal'

    def init(self, cursor, module_name):
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model_data "\
                "SET fs_id = REPLACE(fs_id, 'packing', 'shipment') "\
                "WHERE fs_id like '%%packing%%' AND module = %s",
                (module_name,))
        cursor.execute("UPDATE ir_model "\
                "SET model = REPLACE(model, 'packing', 'shipment') "\
                "WHERE model like '%%packing%%' AND module = %s",
                (module_name,))
        super(ShipmentInternal, self).init(cursor, module_name)

    def generate_internal_shipment(self, cursor, user, context=None):
        """
        Generate internal shipments to meet order points defined on
        non-warehouse location.
        """
        order_point_obj = self.pool.get('stock.order_point')
        uom_obj = self.pool.get('product.uom')
        product_obj = self.pool.get('product.product')
        date_obj = self.pool.get('ir.date')
        user_obj = self.pool.get('res.user')
        user_record = user_obj.browse(cursor, user, user, context=context)
        today = date_obj.today(cursor, user, context=context)
        # fetch quantities on order points
        op_ids = order_point_obj.search(
            cursor, user, [('type', '=', 'internal')], context=context)
        order_points = order_point_obj.browse(
            cursor, user, op_ids, context=context)
        id2product = {}
        location_ids = []
        for op in order_points:
            id2product[op.product.id] = op.product
            location_ids.append(op.storage_location.id)

        local_ctx = context or {}
        local_ctx['stock_date_end'] = today
        pbl = product_obj.products_by_location(
            cursor, user, location_ids, list(id2product.iterkeys()), with_childs=True,
            context=local_ctx)

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
        shipment_ids = self.search(
            cursor, user,
            [('state', '=', 'draft'),
             ['OR', ('planned_date', '<=', today),
              ('planned_date', '=', False)]],
            context=context)
        for shipment in self.browse(cursor, user, shipment_ids, context=context):
            for move in shipment.moves:
                key = (shipment.to_location.id,
                       shipment.from_location.id,
                       move.product.id)
                if key not in moves:
                    continue
                quantity = uom_obj.compute_qty(
                    cursor, user, move.uom, move.quantity,
                    id2product[move.product.id].default_uom, context=context)
                moves[key] = max(0, moves[key] - quantity)

        # Group moves by {from,to}_location
        shipments = {}
        for key,qty in moves.iteritems():
            from_location, to_location, product = key
            shipments.setdefault(
                (from_location, to_location),[]).append((product, qty))
        # Create shipments and moves
        for shipment, moves in shipments.iteritems():
            from_location, to_location = shipment
            values = {
                'from_location': from_location,
                'to_location': to_location,
                'planned_date': today,
                'moves': [],
                }
            for move in moves:
                product, qty = move
                values['moves'].append(
                    ('create',
                     {'from_location': from_location,
                      'to_location': to_location,
                      'product': product,
                      'quantity': qty,
                      'uom': id2product[product].default_uom.id,
                      'company': user_record.company.id,}
                     ))
            self.create(cursor, user, values, context=context)

ShipmentInternal()
