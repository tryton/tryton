#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Move"
from trytond.osv import fields, OSV
from decimal import Decimal
import datetime

STATES = {
    'readonly': "(state in ('cancel', 'done'))",
}


class Move(OSV):
    "Stock Move"
    _name = 'stock.move'
    _description = __doc__
    product = fields.Many2One("product.product", "Product", required=True,
            select=1, states=STATES,
            on_change=['product', 'currency', 'uom', 'company',
                'from_location', 'to_location'],
            domain=[('type', '!=', 'service')])
    uom = fields.Many2One("product.uom", "Uom", required=True, states=STATES,
            domain="[('category', '=', " \
                    "(product, 'product.default_uom.category'))]",
            context="{'category': (product, 'product.default_uom.category')}")
    unit_digits = fields.Function('get_unit_digits', type='integer',
            string='Unit Digits', on_change_with=['uom'])
    quantity = fields.Float("Quantity", required=True,
            digits="(16, unit_digits)", states=STATES)
    from_location = fields.Many2One("stock.location", "From Location", select=1,
            required=True, states=STATES,
            domain=[('type', '!=', 'warehouse')])
    to_location = fields.Many2One("stock.location", "To Location", select=1,
            required=True, states=STATES,
            domain=[('type', '!=', 'warehouse')])
    packing_in = fields.Many2One('stock.packing.in', 'Supplier Packing',
            readonly=True, select=1)
    packing_out = fields.Many2One('stock.packing.out', 'Customer Packing',
            readonly=True, select=1)
    packing_internal = fields.Many2One('stock.packing.internal',
            'Internal Packing', readonly=True, select=1)
    planned_date = fields.Date("Planned Date", states=STATES, select=2)
    effective_date = fields.Date("Effective Date", readonly=True, select=2)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ], 'State', select=1, readonly=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            states={
                'readonly': "state != 'draft'",
            })
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
            states={
                'invisible': "not unit_price_required",
                'required': "unit_price_required",
                'readonly': "state != 'draft'",
            })
    currency = fields.Many2One('currency.currency', 'Currency',
            states={
                'invisible': "not unit_price_required",
                'required': "unit_price_required",
                'readonly': "state != 'draft'",
            })
    unit_price_required = fields.Function('get_unit_price_required',
            type='boolean', string='Unit Price Required',
            on_change_with=['from_location', 'to_location'])

    def __init__(self):
        super(Move, self).__init__()
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
        self._constraints += [
            ('check_product_type', 'service_product'),
        ]
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
            'set_state_draft': 'You can not set state to draft!',
            'set_state_assigned': 'You can not set state to assigned!',
            'set_state_done': 'You can not set state to done!',
            'del_draft_cancel': 'You can only delete draft or cancelled moves!',
            'service_product': 'You can not use service product for a move!',
            })

    def default_planned_date(self, cursor, user, context=None):
        if context and context.get('planned_date'):
            return context.get('planned_date')

    def default_to_location(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        party_obj = self.pool.get('party.party')
        res = False

        if context is None:
            context = {}

        warehouse = None
        if context.get('warehouse'):
            warehouse = location_obj.browse(cursor, user, context['warehouse'],
                    context=context)

        if context.get('type', '') == 'inventory_in':
            if warehouse:
                res = warehouse.storage_location.id
        elif context.get('type', '') == 'inventory_out':
            if warehouse:
                res = warehouse.output_location.id
        elif context.get('type', '') == 'incoming':
            if warehouse:
                res = warehouse.input_location.id
        elif context.get('type', '') == 'outgoing':
            if context.get('customer'):
                customer = party_obj.browse(cursor, user, context['customer'],
                        context=context)
                res = customer.customer_location.id

        if context.get('to_location'):
            res = context.get('to_location')

        if res:
            res = location_obj.name_get(cursor, user, res, context=context)[0]
        return res

    def default_from_location(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        party_obj = self.pool.get('party.party')
        res = False

        if context is None:
            context = {}

        warehouse = None
        if context.get('warehouse'):
            warehouse = location_obj.browse(cursor, user, context['warehouse'],
                    context=context)

        if context.get('type', '') == 'inventory_in':
            if warehouse:
                res = warehouse.input_location.id
        elif context.get('type', '') == 'inventory_out':
            if warehouse:
                res = warehouse.storage_location.id
        elif context.get('type', '') == 'outgoing':
            if warehouse:
                res = warehouse.output_location.id
        elif context.get('type', '') == 'incoming':
            if context.get('supplier'):
                supplier = party_obj.browse(cursor, user, context['supplier'],
                        context=context)
                res = supplier.supplier_location.id

        if context.get('from_location'):
            res = context.get('from_location')

        if res:
            res = location_obj.name_get(cursor, user, res, context=context)[0]
        return res

    def default_state(self, cursor, user, context=None):
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

    def on_change_with_unit_digits(self, cursor, user, ids, vals,
            context=None):
        uom_obj = self.pool.get('product.uom')
        if vals.get('uom'):
            uom = uom_obj.browse(cursor, user, vals['uom'],
                    context=context)
            return uom.digits
        return 2

    def get_unit_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for move in self.browse(cursor, user, ids, context=context):
            res[move.id] = move.uom.digits
        return res

    def on_change_product(self, cursor, user, ids, vals, context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        currency_obj = self.pool.get('currency.currency')
        company_obj = self.pool.get('company.company')
        location_obj = self.pool.get('stock.location')

        if context is None:
            context = {}

        res = {
            'unit_price': Decimal('0.0'),
        }
        if vals.get('product'):
            product = product_obj.browse(cursor, user, vals['product'],
                    context=context)
            res['uom'] = uom_obj.name_get(cursor, user,
                    product.default_uom.id, context=context)[0]
            res['unit_digits'] = product.default_uom.digits
            to_location = None
            if vals.get('to_location'):
                to_location = location_obj.browse(cursor, user,
                        vals['to_location'], context=context)
            if to_location and to_location.type == 'storage':
                unit_price = product.cost_price
                if vals.get('uom') and vals['uom'] != product.default_uom.id:
                    uom = uom_obj.browse(cursor, user, vals['uom'],
                            context=context)
                    unit_price = uom_obj.compute_price(cursor, user,
                            product.default_uom, unit_price, uom,
                            context=context)
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

    def on_change_with_unit_price_required(self, cursor, user, ids, vals,
            context=None):
        location_obj = self.pool.get('stock.location')
        if vals.get('from_location'):
            from_location = location_obj.browse(cursor, user,
                    vals['from_location'], context=context)
            if from_location.type == 'supplier':
                return True
        if vals.get('to_location'):
            to_location = location_obj.browse(cursor, user,
                    vals['to_location'], context=context)
            if to_location.type == 'customer':
                return True
        return False

    def get_unit_price_required(self, cursor, user, ids, name, arg,
            context=None):
        res = {}
        for move in self.browse(cursor, user, ids, context=context):
            res[move.id] = False
            if move.from_location.type == 'supplier':
                res[move.id] = True
            if move.to_location.type == 'customer':
                res[move.id] = True
        return res

    def check_product_type(self, cursor, user, ids):
        for move in self.browse(cursor, user, ids):
            if move.product.type == 'service':
                return False
        return True

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
                    context=None, limit=None):
        if not args:
            args = []
        query = ['AND', ('product', operator, name), args]
        ids = self.search(cursor, user, query, limit=limit, context=context)
        return self.name_get(cursor, user, ids, context)

    def name_get(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        product_obj = self.pool.get('product.product')
        moves = self.browse(cursor, user, ids, context=context)
        pid2name = dict(product_obj.name_get(
                cursor, user, [m.product.id for m in moves], context=context))
        res = []
        for m in moves:
            res.append(
                (m.id,
                 "%s%s %s" % (m.quantity, m.uom.symbol, pid2name[m.product.id]))
                )
        return res

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        location_obj = self.pool.get('stock.location')

        args = args[:]
        def process_args(args):
            i = 0
            while i < len(args):
                if isinstance(args[i], list):
                    process_args(args[i])
                if isinstance(args[i], tuple) \
                        and args[i][0] == 'to_location_warehouse':
                    location_id = False
                    if args[i][2]:
                        location = location_obj.browse(cursor, user,
                                args[i][2], context=context)
                        if location.type == 'warehouse':
                            location_id = location.input_location.id
                    args[i] = ('to_location', args[i][1], location_id)
                i += 1
        process_args(args)
        return super(Move, self).search(cursor, user, args, offset=offset,
                limit=limit, order=order, context=context, count=count,
                query_string=query_string)

    def _update_product_cost_price(self, cursor, user, product_id, quantity, uom,
                                   unit_price, currency, company, context=None):
        """
        Update the cost price on the given product

        :param cursor: the database cursor
        :param user: the user id
        :param product_id: the id of the product
        :param quantity: the quantity of the product, positive if incoming and
                negative if outgoing
        :param uom: the uom id or a BrowseRecord of the uom
        :param unit_price: the unit price of the product
        :param currency: the currency of the unit price
        :param company: the company id ot a BrowseRecord of the company
        :param context: the context
        """
        uom_obj = self.pool.get('product.uom')
        product_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')
        currency_obj = self.pool.get('currency.currency')
        company_obj = self.pool.get('company.company')

        if isinstance(uom, (int, long)):
            uom = uom_obj.browse(cursor, user, uom, context=context)
        if isinstance(company, (int, long)):
            company = company_obj.browse(cursor, user, company, context=context)

        ctx = context and context.copy() or {}
        ctx['locations'] = location_obj.search(
            cursor, user, [('type', '=', 'storage')], context=context)
        ctx['stock_date_end'] = datetime.date.today()
        product = product_obj.browse(cursor, user, product_id, context=ctx)
        qty = uom_obj.compute_qty(
            cursor, user, uom, quantity, product.default_uom, context=context)

        qty = Decimal(str(qty))
        product_qty = Decimal(str(product.template.quantity))
        # convert wrt currency
        unit_price = currency_obj.compute(
            cursor, user, currency, unit_price, company.currency,
            context=context)
        # convert wrt to the uom
        unit_price = uom_obj.compute_price(
            cursor, user, uom, unit_price, product.default_uom, context=context)
        if product_qty + qty != Decimal('0.0'):
            new_cost_price = (
                (product.cost_price * product_qty) + (unit_price * qty)
                ) / (product_qty + qty)
        else:
            new_cost_price = product.cost_price
        product_obj.write(
            cursor, user, product.id, {'cost_price': new_cost_price},
            context=context)

    def create(self, cursor, user, vals, context=None):
        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')

        if vals.get('state') == 'done':
            if not vals.get('effective_date'):
                vals['effective_date'] = datetime.date.today()
            from_location = location_obj.browse(cursor, user,
                    vals['from_location'], context=context)
            to_location = location_obj.browse(cursor, user,
                    vals['to_location'], context=context)
            product = product_obj.browse(cursor, user, vals['product'],
                    context=context)
            if from_location.type == 'supplier' \
                    and product.cost_price_method == 'average':
                self._update_product_cost_price(
                    cursor, user, vals['product'], vals['quantity'],
                    vals['uom'], vals['unit_price'], vals['currency'],
                    vals['company'], context=context)
            if to_location.type == 'supplier' \
                    and product.cost_price_method == 'average':
                self._update_product_cost_price(
                    cursor, user, vals['product'], -vals['quantity'],
                    vals['uom'], vals['unit_price'], vals['currency'],
                    vals['company'], context=context)
        return super(Move, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if 'state' in vals:
            for move in self.browse(cursor, user, ids, context=context):
                if vals['state'] == 'cancel':
                    vals['effective_date'] = False
                    if move.from_location.type == 'supplier' \
                            and move.state != 'cancel' \
                            and move.product.cost_price_method == 'average':
                        self._update_product_cost_price(
                            cursor, user, move.product.id, -move.quantity,
                            move.uom, move.unit_price, move.currency,
                            move.company, context=context)
                    if move.to_location.type == 'supplier' \
                            and move.state != 'cancel' \
                            and move.product.cost_price_method == 'average':
                        self._update_product_cost_price(
                            cursor, user, move.product.id, move.quantity,
                            move.uom, move.unit_price, move.currency,
                            move.company, context=context)

                elif vals['state'] == 'draft':
                    if move.state == 'done':
                        self.raise_user_error(cursor, 'set_state_draft',
                                context=context)
                elif vals['state'] == 'assigned':
                    if move.state in ('cancel', 'done'):
                        self.raise_user_error(cursor, 'set_state_assigned',
                                context=context)
                elif vals['state'] == 'done':
                    if move.state in ('cancel'):
                        self.raise_user_error(cursor, 'set_state_done',
                                context=context)
                    vals['effective_date'] = datetime.date.today()

                    if move.from_location.type == 'supplier' \
                            and move.state != 'done' \
                            and move.product.cost_price_method == 'average':
                        self._update_product_cost_price(
                            cursor, user, move.product.id, move.quantity,
                            move.uom, move.unit_price, move.currency,
                            move.company, context=context)
                    if move.to_location.type == 'supplier' \
                            and move.state != 'done' \
                            and move.product.cost_price_method == 'average':
                        self._update_product_cost_price(
                            cursor, user, move.product.id, -move.quantity,
                            move.uom, move.unit_price, move.currency,
                            move.company, context=context)

        return super(Move, self).write(cursor, user, ids, vals, context=context)

    def delete(self, cursor, user, ids, context=None):
        for move in self.browse(cursor, user, ids, context=context):
            if move.state not in  ('draft', 'cancel'):
                self.raise_user_error(cursor, 'del_draft_cancel',
                        context=context)
        return super(Move, self).delete(cursor, user, ids, context=context)

Move()
