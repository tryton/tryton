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
        "product.product", "Product", required=True, select=1, states=STATES,
        on_change=['product'])
    uom = fields.Many2One("product.uom", "Uom", required=True, states=STATES,)
    quantity = fields.Float(
        "Quantity", digits=(12, 6), required=True,
        states=STATES,)
    from_location = fields.Many2One(
        "stock.location", "From Location", select=1, required=True,
        states=STATES, domain="[('type', '!=', 'warehouse')]",)
    to_location = fields.Many2One(
        "stock.location", "To Location", select=1, required=True,
        states=STATES, domain="[('type', '!=', 'warehouse')]",)
    packing_in = fields.Many2One('stock.packing.in', 'Supplier Packing',
            readonly=True, select=1)
    packing_out = fields.Many2One('stock.packing.out', 'Customer Packing',
            readonly=True, select=1)
    planned_date = fields.Date("Planned Date", states=STATES,)
    effective_date = fields.Date("Effective Date", readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ('waiting', 'Waiting'),
        ('assigned', 'Assigned'),
        ], 'State', select=1, readonly=True)

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
            ('check_from_to_locations',
                'CHECK(from_location != to_location)',
                'Source and destination location must be different'),
            ('check_packing_in_out',
                'CHECK(NOT(packing_in IS NOT NULL ' \
                        'AND packing_out IS NOT NULL))',
                'Move can not be in both Supplier and Customer Packing'),
        ]
        self._order[0] = ('id', 'DESC')

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
        if not context: return 'draft'
        if context.get('type') == 'incoming':
            if context['packing_state'] == 'waiting':
                return 'waiting'
            if context['packing_state'] in ('received', 'done'):
                return 'done'
        if context.get('type') == 'inventory_in':
            if context['packing_state'] == 'received':
                return 'waiting'
            if context['packing_state'] == 'done':
                return 'done'
        if context.get('type') == 'outgoing':
            if context['packing_state'] == 'ready':
                return 'waiting'
            if context['packing_state'] == 'done':
                return 'done'
        if context.get('type') == 'inventory_out':
            if context['packing_state'] in ('waiting','assigned'):
                return context['packing_state']
            if context['packing_state'] in ('ready','done'):
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
            cursor, user, ids, ['draft', 'waiting', 'assigned'],
            {'state': 'done',
             'effective_date': time.strftime('%Y-%m-%d %H:%M:%S')})

    def set_state_draft(self, cursor, user, ids, context=None):
        self.set_by_state(
            cursor, user, ids, ['cancel', 'waiting'],
            {'state': 'draft',})

    def set_state_cancel(self, cursor, user, ids, context=None):
        self.set_by_state(
            cursor, user, ids, ['done', 'waiting', 'assigned'],
            {'state': 'cancel',})

    def set_state_waiting(self, cursor, user, ids, context=None):
        self.set_by_state(
            cursor, user, ids, ['draft',],
            {'state':'waiting',})

    def set_state_assigned(self, cursor, user, ids, context=None):
        self.set_by_state(
            cursor, user, ids, ['draft', 'waiting'],
            {'state': 'waiting',})

    def unlink(self, cursor, user, ids, context=None):
        move_ids = self.search(
            cursor, user, [('id', 'in', ids), ('state', 'in',
            ['done', 'waiting', 'cancel'])], context)
        if move_ids:
            raise ExceptORM('UserError', 'You can only delete draft moves !')
        return super(Move, self).unlink(cursor, user, ids, context=context)

Move()
