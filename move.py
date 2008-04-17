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
    _order = "id DESC"
    _rec_name = "product"
    product = fields.Many2One(
        "product.product", "Product", required=True, select=True, states=STATES,
        on_change=['product'])
    uom = fields.Many2One("product.uom", "Uom", required=True, states=STATES,)
    quantity = fields.Float(
        "Quantity", digits=(12, 6), required=True,
        states=STATES,)
    from_location =fields.Many2One(
        "stock.location", "From Location", select=True, required=True,
        states=STATES,)
    to_location = fields.Many2One(
        "stock.location", "To Location", select=True, required=True,
        states=STATES,)
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
    packing_out = fields.Many2One(
        "stock.packing.out", "Customer Packing", states=STATES, select=True)
    planned_date = fields.Date("Planned Date", states=STATES,)
    effective_date = fields.Date("Effective Date", readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'),('done', 'Done'),('cancel', 'Cancel'),
         ('waiting', 'Waiting')], 'State', select=True, readonly=True)


    # TODO : constrains: moves on the same packing must share the
    # same locations (and this location must own to the selected wh.)

    def __init__(self):
        super(Move, self).__init__()
        self._rpc_allowed += [
            'set_state_done',
            'set_state_waiting',
            'set_state_draft',
            'set_state_cancel',
            ]

    def default_to_location(self, cursor, user, context=None):
        if context and context.get('wh_incoming'):
            warehouse = self.pool.get('stock.warehouse').browse(
                cursor, user, context['wh_incoming'], context=context)
            return warehouse.input_location.id
        if context and context.get('wh_inv_out'):
            warehouse = self.pool.get('stock.warehouse').browse(
                cursor, user, context['wh_inv_out'], context=context)
            return warehouse.output_location.id
        return False

    def default_from_location(self, cursor, user, context=None):
        if context and context.get('wh_inv_in'):
            warehouse = self.pool.get('stock.warehouse').browse(
                cursor, user, context['wh_inv_in'], context=context)
            return warehouse.input_location.id
        if context and context.get('wh_outgoing'):
            warehouse = self.pool.get('stock.warehouse').browse(
                cursor, user, context['wh_outgoing'], context=context)
            return warehouse.output_location.id
        return False

    def default_state(self, cursor, user, context=None):
        if not context: return 'draft'
        if 'pack_incoming_state' in context:
            if context['pack_incoming_state'] == 'waiting':
                return 'waiting'
            if context['pack_incoming_state'] in ('received', 'done'):
                return 'done'
        if 'pack_inv_in_state' in context:
            if context['pack_inv_in_state'] == 'received':
                return 'waiting'
            if context['pack_inv_in_state'] == 'done':
                return 'done'
        if 'pack_outgoing_state' in context:
            if context['pack_outgoing_state'] in \
                    ('waiting', 'assigned', 'ready'):
                return 'waiting'
            if context['pack_outgoing_state'] in 'done':
                return 'done'
        if 'pack_inv_out_state' in context:
            if context['pack_inv_out_state'] == 'assigned':
                return 'waiting'
            if context['pack_inv_out_state'] == 'ready':
                return 'done'

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
        warehouse_obj = self.pool.get('stock.warehouse')

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
        warehouse_ids = warehouse_obj.search(
            cursor, user,
            [('input_location', 'in',
              [l for l in moves_by_location])])
        warehouses = warehouse_obj.browse(
            cursor, user, warehouse_ids, context=context)
        loc2wh = dict([( wh.input_location.id, wh.id) for wh in warehouses])

        packing_ids = []
        for location, move_ids in moves_by_location.iteritems():
            wh = loc2wh.get(location)
            if not wh:
                raise ExceptWizard(
                    'UserError',
                    'Moves must have a final destination '\
                    'who is an input location of a wharehouse.')
            pid = packing_obj.create(
                cursor, user,
                {'incoming_moves': [('set',move_ids)], 'warehouse': wh},
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

