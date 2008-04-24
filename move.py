"Move"
from trytond.osv import fields, OSV, ExceptORM
from trytond.wizard import Wizard, WizardOSV, ExceptWizard
import time

STATES = {
    'readonly': "(state in ('cancel', 'done'))",
}

class Move(OSV):
    "Stock Move"
    _name = 'stock.move'
    _description = __doc__
    _rec_name = "product"
    product = fields.Many2One(
        "product.product", "Product", required=True, select=True, states=STATES,
        on_change=['product'])
    uom = fields.Many2One("product.uom", "Uom", required=True, states=STATES,)
    quantity = fields.Float(
        "Quantity", digits=(12, 6), required=True,
        states=STATES,)
    from_location = fields.Many2One(
        "stock.location", "From Location", select=True, required=True,
        states=STATES, domain="[('type', '!=', 'warehouse')]",)
    to_location = fields.Many2One(
        "stock.location", "To Location", select=True, required=True,
        states=STATES, domain="[('type', '!=', 'warehouse')]",)
    incoming_packing_in = fields.Many2One(
        "stock.packing.in", "Supplier Packing", states=STATES, select=True)
    inventory_packing_in = fields.Many2One(
        "stock.packing.in", "Inventory Supplier Packing", states=STATES,
        select=True)
    outgoing_packing_out = fields.Many2One(
        "stock.packing.out", "Customer Packing", states=STATES, select=True)
    inventory_packing_out = fields.Many2One(
        "stock.packing.out", "Inventory Customer Packing", states=STATES,
        select=True)
    planned_date = fields.Date("Planned Date", states=STATES,)
    effective_date = fields.Date("Effective Date", readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'),('done', 'Done'),('cancel', 'Cancel'),
         ('waiting', 'Waiting')], 'State', select=True, readonly=True)


    def __init__(self):
        super(Move, self).__init__()
        self._rpc_allowed += [
            'set_state_done',
            'set_state_waiting',
            'set_state_draft',
            'set_state_cancel',
            ]
        self._sql_constraints += [
            ('check_move_qty_pos',
                'CHECK(quantity >= 0.0)', 'Move quantity must be positive'),
        ]
        self._constraints += [
            ('check_locations',
                'Invalid locations', []),
        ]
        self._order[0] = ('id', 'DESC')

    def check_locations(self, cursor, user, ids, context=None):
        for move in self.browse(cursor, user, ids, context=context):
            if move.from_location.id == move.to_location.id:
                return False
            if move.incoming_packing_in:
                if move.incoming_packing_in.warehouse.input_location.id \
                        != move.to_location.id:
                    return False
                if move.from_location.type and \
                        move.from_location.type not in ('supplier', 'customer'):
                    return False
                for packing_move in move.incoming_packing_in.incoming_moves:
                    if packing_move.from_location.id != move.from_location.id:
                        return False
            if move.inventory_packing_in and \
                    move.inventory_packing_in.warehouse.input_location.id \
                    != move.from_location.id:
                return False
            if move.inventory_packing_out and \
                    move.inventory_packing_out.warehouse.output_location.id \
                    != move.to_location.id:
                return False
            if move.outgoing_packing_out:
                if move.outgoing_packing_out.warehouse.output_location.id \
                        != move.from_location.id:
                    return False
                if move.to_location.type and \
                        move.to_location.type not in ('supplier','customer'):
                    return False
                for packing_move in move.outgoing_packing_out.outgoing_moves:
                    if packing_move.to_location.id != move.to_location.id:
                        return False
        return True

    def default_to_location(self, cursor, user, context=None):
        if context and context.get('warehouse') and context.get('type'):
            wh_location = self.pool.get('stock.location').browse(
                cursor, user, context['warehouse'], context=context)
            field = {'inventory_in': 'storage_location',
                     'inventory_out': 'output_location',
                     'incoming': 'input_location',}.get(context['type'])
            return field and wh_location[field].id or False

    def default_from_location(self, cursor, user, context=None):
        if context and context.get('warehouse') and context.get('type'):
            wh_location = self.pool.get('stock.location').browse(
                cursor, user, context['warehouse'], context=context)
            field = {'inventory_in': 'input_location',
                     'inventory_out': 'storage_location',
                     'outgoing': 'output_location',}.get(context['type'])
            return field and wh_location[field].id or False

    def default_state(self, cursor, user, context=None):
#TODO
#         if not context: return 'draft'
#         if 'pack_incoming_state' in context:
#             if context['pack_incoming_state'] == 'waiting':
#                 return 'waiting'
#             if context['pack_incoming_state'] in ('received', 'done'):
#                 return 'done'
#         if 'pack_inv_in_state' in context:
#             if context['pack_inv_in_state'] == 'received':
#                 return 'waiting'
#             if context['pack_inv_in_state'] == 'done':
#                 return 'done'
#         if 'pack_outgoing_state' in context:
#             if context['pack_outgoing_state'] in \
#                     ('waiting', 'assigned', 'ready'):
#                 return 'waiting'
#             if context['pack_outgoing_state'] in 'done':
#                 return 'done'
#         if 'pack_inv_out_state' in context:
#             if context['pack_inv_out_state'] == 'assigned':
#                 return 'waiting'
#             if context['pack_inv_out_state'] == 'ready':
#                 return 'done'
        return 'draft'

    def on_change_product(self, cursor, user, ids, value, context=None):
        if 'product' in value and value['product']:
            product = self.pool.get('product.product').browse(
                cursor, user, value['product'])
            return {'uom': product.default_uom.id}
        return {}

    def set_by_state(self, cursor, user, ids, from_states, values,
                     context=None):
        move_ids = self.search(
            cursor, user, [('id', 'in', ids),
                           ('state', 'in', from_states)])
        return self.write(cursor, user, move_ids, values, context=context)

    def set_state_done(self, cursor, user, ids, context=None):
        self.set_by_state(
            cursor, user, ids, ['draft', 'waiting'],
            {'state':'done',
             'effective_date': time.strftime('%Y-%m-%d %H:%M:%S')})

    def set_state_draft(self, cursor, user, ids, context=None):
        self.set_by_state(
            cursor, user, ids, ['cancel', 'waiting'],
            {'state':'draft',})

    def set_state_cancel(self, cursor, user, ids, context=None):
        self.set_by_state(
            cursor, user, ids, ['done', 'waiting'],
            {'state':'cancel',})
    def set_state_waiting(self, cursor, user, ids, context=None):
        self.set_by_state(
            cursor, user, ids, ['draft',],
            {'state':'waiting',})

    def unlink(self, cursor, user, ids, context=None):
        move_ids = self.search(
            cursor, user, [('id', 'in',ids),('state', 'in',
            ['done', 'waiting', 'cancel'])], context)

        if move_ids:
            raise ExceptORM('UserError', 'You can only delete draft moves !')

        return super(Move, self).unlink(cursor, user, ids, context=context)
Move()


class CreatePackingWarn(WizardOSV):
    _name = 'stock.move.create_packing.warn'
CreatePackingWarn()

class CreatePacking(Wizard):
    'Create Packing'
    _name = 'stock.move.create_packing'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_create',
                'state': 'end',
                },
            },

        }
    def _create(self, cursor, user, data, context=None):

        move_obj = self.pool.get('stock.move')
        packing_obj = self.pool.get('stock.packing.in')
        location_obj = self.pool.get('stock.location')

        moves = move_obj.browse(cursor, user, data['ids'], context=context)
        # Collect moves by incoming location
        moves_by_location = {}
        for move in moves:
            if move.incoming_packing_in or move.inventory_packing_in:
                raise ExceptWizard(
                    'UserError', 'Moves cannot be already in a packing.')
            if move.state != 'waiting':
                raise ExceptWizard(
                    'UserError', 'Moves must be in waiting state.')

            location = move.to_location.id
            if location not in moves_by_location:
                moves_by_location[location] = [move.id]
            else:
                moves_by_location[location].append(move.id)

        # Fetch warehouse for these locations
        wh_location_ids = location_obj.search(
            cursor, user,
            [('input_location', 'in',
              [l for l in moves_by_location]),
             ('type','=','warehouse')], context=context)
        wh_locations = location_obj.browse(
            cursor, user, warehouse_ids, context=context)
        loc2wh = dict([( whl.input_location.id, whl.id) for whl in wh_locations])

        packing_ids = []
        for location, move_ids in moves_by_location.iteritems():
            whl = loc2wh.get(location)
            if not whl:
                raise ExceptWizard(
                    'UserError',
                    'Moves must have a final destination '\
                    'who is an input location of a wharehouse.')
            pid = packing_obj.create(
                cursor, user,
                {'incoming_moves': [('set',move_ids)], 'warehouse': whl},
                context=context)

            packing_ids.append(pid)

        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_packing_in_form'),
            ('module', '=', 'stock'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id,
                                  context=context)
        res["domain"]= str([('id', 'in',packing_ids)])

        return res

CreatePacking()

