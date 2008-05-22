"Move"
from trytond.osv import fields, OSV, ExceptORM
from trytond.wizard import Wizard, WizardOSV, ExceptWizard
import time
from decimal import Decimal
import datetime

STATES = {
    'readonly': "(state in ('cancel', 'done'))",
}


class Move(OSV):
    "Stock Move"
    _name = 'stock.move'
    _description = __doc__
    _rec_name = "product"
    product = fields.Many2One("product.product", "Product", required=True,
            select=1, states=STATES,
            on_change=['product', 'type', 'currency', 'uom', 'company'])
    uom = fields.Many2One("product.uom", "Uom", required=True, states=STATES)
    quantity = fields.Float("Quantity", digits=(12, 6), required=True,
            states=STATES)
    from_location = fields.Many2One("stock.location", "From Location", select=1,
            required=True, states=STATES,
            domain=[('type', '!=', 'warehouse')],
            on_change=['from_location', 'to_location'])
    to_location = fields.Many2One("stock.location", "To Location", select=1,
            required=True, states=STATES,
            domain=[('type', '!=', 'warehouse')],
            on_change=['from_location', 'to_location'])
    packing_in = fields.Many2One('stock.packing.in', 'Supplier Packing',
            readonly=True, select=1)
    packing_out = fields.Many2One('stock.packing.out', 'Customer Packing',
            readonly=True, select=1)
    planned_date = fields.Date("Planned Date", states=STATES)
    effective_date = fields.Date("Effective Date", readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ('waiting', 'Waiting'),
        ('assigned', 'Assigned'),
        ], 'State', select=1, readonly=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            states={
                'readonly': "state != 'draft'",
            })
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
            states={
                'invisible': "type not in ('input', 'output')",
                'required': "type in ('input', 'output')",
                'readonly': "state not in ('draft', 'waiting')",
            })
    currency = fields.Many2One('currency.currency', 'Currency',
            states={
                'invisible': "type not in ('input', 'output')",
                'required': "type in ('input', 'output')",
                'readonly': "state not in ('draft', 'waiting')",
            })
    type = fields.Function('get_type', type='selection',
            selection=[
                ('input', 'Input'),
                ('output', 'Output'),
                ('internal', 'Internal'),
            ], string='Type')

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

    def default_company(self, cursor, user, context=None):
        if context.get('company'):
            return context.get('company')
        user_obj = self.pool.get('res.user')
        user = user_obj.browse(cursor, user, user, context=context)
        return user.company.id

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

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

    def default_currency(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        if context is None:
            context = {}
        company = None
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return currency_obj.name_get(cursor, user, company.currency.id,
                    context=context)[0]
        return False

    def get_type(self, cursor, user, ids, name, args, context=None):
        res = {}
        for move in self.browse(cursor, user, ids, context=context):
            res[move.id] = 'internal'
            if move.from_location.type == 'supplier':
                res[move.id] = 'input'
            if move.to_location.type == 'customer':
                res[move.id] = 'output'
        return res

    def on_change_product(self, cursor, user, ids, vals, context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        currency_obj = self.pool.get('currency.currency')
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        res = {'unit_price': Decimal('0.0')}
        if vals.get('product'):
            product = product_obj.browse(cursor, user, vals['product'],
                    context=context)
            res['uom'] = uom_obj.name_get(cursor, user,
                    product.default_uom.id, context=context)[0]
            if vals.get('type', 'internal') == 'input':
                unit_price = product.cost_price
                if vals.get('uom') and vals['uom'] != product.default_uom.id:
                    unit_price = uom_obj.compute_price(cursor, user,
                            product.default_uom, unit_price, vals['uom'])
                if vals.get('currency') and vals.get('company'):
                    currency = currency_obj.browse(cursor, user,
                            vals['currency'], context=context)
                    company = company_obj.browse(cursor, user,
                            vals['company'], context=context)
                    unit_price = currency_obj.compute(cursor, user,
                            company.currency, unit_price, currency,
                            context=context)
                res['unit_price'] = unit_price
        return res

    def _on_change_location(self, cursor, user, ids, vals, context=None):
        location_obj = self.pool.get('stock.location')
        res = {'type': 'internal'}
        if vals.get('from_location'):
            location = location_obj.browse(cursor, user, vals['from_location'],
                    context=context)
            if location.type == 'supplier':
                res['type'] = 'input'
        if vals.get('to_location'):
            location = location_obj.browse(cursor, user, vals['to_location'],
                    context=context)
            if location.type == 'customer':
                res['type'] = 'output'
        return res

    def on_change_from_location(self, cursor, user, ids, vals, context=None):
        return self._on_change_location(cursor, user, ids, vals,
                context=context)

    def on_change_to_location(self, cursor, user, ids, vals, context=None):
        return self._on_change_location(cursor, user, ids, vals,
                context=context)

    def set_state_done(self, cursor, user, ids, context=None):
        return self.write(cursor, user, ids, {
            'state': 'done',
            'effective_date': datetime.datetime.now(),
            }, context=context)

    def set_state_draft(self, cursor, user, ids, context=None):
        return self.write(cursor, user, ids, {
            'state': 'draft',
            }, context=context)

    def set_state_cancel(self, cursor, user, ids, context=None):
        return self.write(cursor, user, ids, {
            'state': 'cancel',
            }, context=context)

    def set_state_waiting(self, cursor, user, ids, context=None):
        return self.write(cursor, user, ids, {
            'state': 'waiting',
            }, context=context)

    def set_state_assigned(self, cursor, user, ids, context=None):
        return self.write(cursor, user, ids, {
            'state': 'assigned',
            }, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        uom_obj = self.pool.get('product.uom')
        product_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if 'state' in vals:
            for move in self.browse(cursor, user, ids, context=context):
                if vals['state'] == 'draft':
                    if move.state in ('assigned', 'done'):
                        raise ExceptORM('UserError', 'You can not set ' \
                                'state to draft!')
                elif vals['state'] == 'waiting':
                    if move.state in ('cancel', 'assigned', 'done'):
                        raise ExceptORM('UserError', 'You can not set ' \
                                'state to waiting!')
                elif vals['state'] == 'assigned':
                    if move.state in ('cancel', 'done'):
                        raise ExceptORM('UserError', 'You can not set ' \
                                'state to assigned!')
                elif vals['state'] == 'done':
                    if move.state in ('cancel'):
                        raise ExceptORM('UserError', 'You can not set ' \
                                'state to done!')
                    if move.type == 'input' \
                            and move.product.cost_price_method == 'average':
                        ctx = context.copy()
                        ctx['locations'] = location_obj.search(cursor, user, [
                            ('type', 'in', 'storage'),
                            ], context=context)
                        product = product_obj.browse(cursor, user,
                                move.product.id, context=ctx)

                        qty = uom_obj.compute_qty(cursor, user, move.uom,
                                move.quantity, product.default_uom)

                        if qty > 0:
                            qty = Decimal(str(qty))
                            product_qty = Decimal(str(product.quantity))
                            unit_price = uom_obj.compute_price(cursor, user,
                                    move.uom, move.unit_price, product.default_uom)
                            new_cost_price = (\
                                    (product.cost_price * product_qty) \
                                    + (unit_price * qty)) \
                                    / (product_qty + qty)
                            product_obj.write(cursor, user, product.id, {
                                'cost_price': new_cost_price,
                                }, context=context)
        return super(Move, self).write(cursor, user, ids, vals, context=context)

    def unlink(self, cursor, user, ids, context=None):
        move_ids = self.search(
            cursor, user, [('id', 'in', ids), ('state', 'in',
            ['done', 'waiting'])], context)
        if move_ids:
            raise ExceptORM('UserError', 'You can only delete draft moves !')
        return super(Move, self).unlink(cursor, user, ids, context=context)

Move()
