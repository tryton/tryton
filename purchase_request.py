#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import operator
from itertools import groupby
from functools import partial
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.pyson import If, In, Eval, Get
from trytond.transaction import Transaction
from trytond.pool import Pool


class PurchaseRequest(ModelSQL, ModelView):
    'Purchase Request'
    _name = 'purchase.request'
    _description = __doc__

    product = fields.Many2One('product.product', 'Product', required=True,
        select=True, readonly=True, domain=[('purchasable', '=', True)])
    party = fields.Many2One('party.party', 'Party',  select=True)
    quantity = fields.Float('Quantity', required=True)
    uom = fields.Many2One('product.uom', 'UOM', required=True, select=True)
    computed_quantity = fields.Float('Computed Quantity', readonly=True)
    computed_uom = fields.Many2One('product.uom', 'Computed UOM',
        readonly=True)
    purchase_date = fields.Date('Best Purchase Date', readonly=True)
    supply_date = fields.Date('Expected Supply Date', readonly=True)
    stock_level = fields.Float('Stock at Supply Date', readonly=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse",
        states={
            'required': Eval('warehouse_required', False),
            },
        domain=[('type', '=', 'warehouse')], depends=['warehouse_required'],
        readonly=True)
    warehouse_required = fields.Function(fields.Boolean('Warehouse Required'),
        'get_warehouse_required')
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
        readonly=True)
    purchase = fields.Function(fields.Many2One('purchase.purchase',
        'Purchase'), 'get_purchase')
    company = fields.Many2One('company.company', 'Company', required=True,
            readonly=True, domain=[
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Get(Eval('context', {}), 'company', 0)),
            ])
    origin = fields.Reference('Origin', selection='origin_get', readonly=True,
            required=True)
    state = fields.Function(fields.Selection([
        ('purchased', 'Purchased'),
        ('done', 'Done'),
        ('draft', 'Draft'),
        ('cancel', 'Cancel'),
        ], 'State'), 'get_state')

    def __init__(self):
        super(PurchaseRequest, self).__init__()
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
                'create_request': 'Purchase requests are only created ' \
                    'by the system.',
                })
        self._sql_constraints += [
            ('check_purchase_request_quantity', 'CHECK(quantity > 0)',
                'The requested quantity must be greater than 0'),
            ]

    def init(self, module_name):
        cursor = Transaction().cursor
        super(PurchaseRequest, self).init(module_name)

        # Migration from 2.0: empty order point origin is -1 instead of 0
        cursor.execute('UPDATE "%s" '
            'SET origin = %%s WHERE origin = %%s' % self._table,
            ('stock.order_point,-1', 'stock.order_point,0'))

    def get_rec_name(self, ids, name):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for pr in self.browse(ids):
            if pr.warehouse:
                res[pr.id] = "%s@%s" % (pr.product.name, pr.warehouse.name)
            else:
                res[pr.id] = pr.product.name
        return res

    def search_rec_name(self, name, clause):
        res = []
        names = clause[2].split('@', 1)
        res.append(('product.template.name', clause[1], names[0]))
        if len(names) != 1 and names[1]:
            res.append(('warehouse', clause[1], names[1]))
        return res

    def default_company(self):
        return Transaction().context.get('company')

    def get_purchase(self, ids, name):
        res = {}

        requests = self.browse(ids)
        for request in requests:
            if request.purchase_line:
                res[request.id] = request.purchase_line.purchase.id
            else:
                res[request.id] = None
        return res

    def get_state(self, ids, name):
        res = {}.fromkeys(ids, 'draft')
        for request in self.browse(ids):
            if request.purchase_line:
                if request.purchase_line.purchase.state == 'cancel':
                    res[request.id] = 'cancel'
                elif request.purchase_line.purchase.state == 'done':
                    res[request.id] = 'done'
                else:
                    res[request.id] = 'purchased'
        return res

    def get_warehouse_required(self, ids, name):
        requireds = {}
        for request in self.browse(ids):
            requireds[request.id] = request.product.type in ('goods', 'assets')
        return requireds

    def origin_get(self):
        model_obj = Pool().get('ir.model')
        res = []
        model_ids = model_obj.search([
            ('model', '=', 'stock.order_point'),
            ])
        for model in model_obj.browse(model_ids):
            res.append([model.model, model.name])
        return res

    def generate_requests(self):
        """
        For each product compute the purchase request that must be
        create today to meet product outputs.
        """
        pool = Pool()
        order_point_obj = pool.get('stock.order_point')
        product_obj = pool.get('product.product')
        location_obj = pool.get('stock.location')
        user_obj = pool.get('res.user')
        company = user_obj.browse(Transaction().user).company

        # fetch warehouses:
        warehouse_ids = location_obj.search([
                ('type', '=', 'warehouse'),
                ])
        # fetch order points
        order_point_ids = order_point_obj.search([
            ('type', '=', 'purchase'),
            ])
        # index them by product
        product2ops = {}
        for order_point in order_point_obj.browse(order_point_ids):
            product2ops[
                (order_point.warehouse_location.id, order_point.product.id)
                ] = order_point

        # fetch goods
        product_ids = product_obj.search([
                ('type', '=', 'goods'),
                ('consumable', '=', False),
                ('purchasable', '=', True),
                ])
        #aggregate product by minimum supply date
        date2products = {}
        for product in product_obj.browse(product_ids):
            min_date, max_date = self.get_supply_dates(product)
            date2products.setdefault((min_date, max_date), []).append(product)

        # compute requests
        new_requests = []
        cursor = Transaction().cursor
        for dates, products in date2products.iteritems():
            min_date, max_date = dates
            for i in range(0, len(products), cursor.IN_MAX):
                product_ids = [p.id for p in products[i:i + cursor.IN_MAX]]
                with Transaction().set_context(forecast=True,
                        stock_date_end=min_date or datetime.date.max):
                    pbl = product_obj.products_by_location(warehouse_ids,
                        product_ids, with_childs=True, skip_zero=False)
                for warehouse_id in warehouse_ids:
                    min_date_qties = dict((x, pbl.pop((warehouse_id, x)))
                        for x in product_ids)
                    # Search for shortage between min-max
                    shortages = self.get_shortage(warehouse_id, product_ids,
                        min_date, max_date, min_date_qties=min_date_qties,
                        order_points=product2ops)

                    for product in products[i:i + cursor.IN_MAX]:
                        shortage_date, product_quantity = shortages[product.id]
                        if shortage_date == None or product_quantity == None:
                            continue
                        order_point = product2ops.get(
                            (warehouse_id, product.id))
                        # generate request values
                        request_val = self.compute_request(product,
                            warehouse_id, shortage_date, product_quantity,
                            company, order_point)
                        new_requests.append(request_val)

        new_requests = self.compare_requests(new_requests)

        self.create_requests(new_requests)
        return {}

    def create_requests(self, new_requests):
        request_obj = Pool().get('purchase.request')

        for new_req in new_requests:
            if new_req['supply_date'] == datetime.date.max:
                new_req['supply_date'] = None
            if new_req['quantity'] > 0.0:
                new_req.update({
                        'product': new_req['product'].id,
                        'party': new_req['party'] and new_req['party'].id,
                        'uom': new_req['uom'].id,
                        'computed_uom': new_req['computed_uom'].id,
                        'company': new_req['company'].id
                        })
                request_obj.create(new_req)

    def compare_requests(self, new_requests):
        """
        Compare new_requests with already existing request to avoid
        to re-create existing requests.
        """
        # delete purchase request without a purchase line
        pool = Pool()
        uom_obj = pool.get('product.uom')
        request_obj = pool.get('purchase.request')
        req_ids = request_obj.search([
            ('purchase_line', '=', None),
            ('origin', 'like', 'stock.order_point,%'),
            ])
        request_obj.delete(req_ids)

        req_ids = request_obj.search([
                ('purchase_line.moves', '=', None),
                ('purchase_line.purchase.state', '!=', 'cancel'),
                ('origin', 'like', 'stock.order_point,%'),
                ])
        requests = request_obj.browse(req_ids)
        # Fetch data from existing requests
        existing_req = {}
        for request in requests:
            pline = request.purchase_line
            # Skip incoherent request
            if request.product.id != pline.product.id or \
                    request.warehouse.id != pline.purchase.warehouse.id:
                continue
            # Take smallest amount between request and purchase line
            req_qty = uom_obj.compute_qty(request.uom, request.quantity,
                    pline.unit)
            if req_qty < pline.quantity:
                quantity = request.quantity
                uom = request.uom
            else:
                quantity = pline.quantity
                uom = pline.unit

            existing_req.setdefault(
                (request.product.id, request.warehouse.id),
                []).append({
                        'supply_date': \
                            request.supply_date or datetime.date.max,
                        'quantity': quantity,
                        'uom': uom,
                        })

        for i in existing_req.itervalues():
            i.sort(lambda r, s: cmp(r['supply_date'], s['supply_date']))

        # Update new requests to take existing requests into account
        new_requests.sort(key=operator.itemgetter('supply_date'))
        for new_req in new_requests:
            for old_req in existing_req.get((new_req['product'].id,
                                             new_req['warehouse']), []):
                if old_req['supply_date'] <= new_req['supply_date']:
                    quantity = uom_obj.compute_qty(old_req['uom'],
                            old_req['quantity'], new_req['uom'])
                    new_req['quantity'] = max(0.0,
                        new_req['quantity'] - quantity)
                    new_req['computed_quantity'] = new_req['quantity']
                    old_req['quantity'] = uom_obj.compute_qty(new_req['uom'],
                        max(0.0, quantity - new_req['quantity']),
                        old_req['uom'])
                else:
                    break

        return new_requests

    def get_supply_dates(self, product):
        """
        Return the minimal interval of earliest supply dates for a product.

        :param product: a BrowseRecord of the Product
        :return: a tuple with the two dates
        """
        product_supplier_obj = Pool().get('purchase.product_supplier')
        date_obj = Pool().get('ir.date')

        min_date = None
        max_date = None
        today = date_obj.today()

        for product_supplier in product.product_suppliers:
            supply_date = product_supplier_obj.compute_supply_date(
                    product_supplier, date=today)
            # TODO next_day is by default today + 1 but should depends
            # on the CRON activity
            next_day = today + datetime.timedelta(1)
            next_supply_date = product_supplier_obj.compute_supply_date(
                            product_supplier, date=next_day)
            if (not min_date) or supply_date < min_date:
                min_date = supply_date
            if (not max_date):
                max_date = next_supply_date
            if supply_date > min_date and supply_date < max_date:
                max_date = supply_date
            if next_supply_date < max_date:
                max_date = next_supply_date

        if not min_date:
            min_date = datetime.date.max
            max_date = datetime.date.max

        return (min_date, max_date)

    def find_best_supplier(self, product, date):
        '''
        Return the best supplier and purchase_date for the product.
        '''
        pool = Pool()
        date_obj = pool.get('ir.date')
        product_supplier_obj = pool.get('purchase.product_supplier')

        supplier = None
        timedelta = datetime.timedelta.max
        today = date_obj.today()
        for product_supplier in product.product_suppliers:
            supply_date = product_supplier_obj.compute_supply_date(
                    product_supplier, date=today)
            sup_timedelta = date - supply_date
            if not supplier:
                supplier = product_supplier.party
                timedelta = sup_timedelta
                continue

            if timedelta < datetime.timedelta(0) \
                    and (sup_timedelta >= datetime.timedelta(0) \
                    or sup_timedelta > timedelta):
                supplier = product_supplier.party
                timedelta = sup_timedelta

        if supplier:
            purchase_date = product_supplier_obj.compute_purchase_date(
                    product_supplier, date)
        else:
            purchase_date = today
        return supplier, purchase_date

    def compute_request(self, product, location_id, shortage_date,
            product_quantity, company, order_point=None):
        """
        Return the value of the purchase request which will answer to
        the needed quantity at the given date. I.e: the latest
        purchase date, the expected supply date and the prefered
        supplier.
        """
        pool = Pool()
        uom_obj = pool.get('product.uom')

        supplier, purchase_date = self.find_best_supplier(product,
            shortage_date)

        max_quantity = order_point and order_point.max_quantity or 0.0
        quantity = uom_obj.compute_qty(product.default_uom,
                max_quantity - product_quantity,
                product.purchase_uom or product.default_uom)

        if order_point:
            origin = 'stock.order_point,%s' % order_point.id
        else:
            origin = 'stock.order_point,-1'
        return {'product': product,
                'party': supplier and supplier or None,
                'quantity': quantity,
                'uom': product.purchase_uom or product.default_uom,
                'computed_quantity': quantity,
                'computed_uom': product.purchase_uom or product.default_uom,
                'purchase_date': purchase_date,
                'supply_date': shortage_date,
                'stock_level': product_quantity,
                'company': company,
                'warehouse': location_id,
                'origin': origin,
                }

    def get_shortage(self, location_id, product_ids, min_date, max_date,
            min_date_qties, order_points):
        """
        Return for each product the first date between min_date and max_date
        where the stock quantity is less than the minimal quantity and the
        smallest stock quantity in the interval or None if there is no date
        where stock quantity is less than the minimal quantity.

        The minimal quantity comes from the order point or is zero.

        min_date_qty is the quantities for each products at the min_date.
        order_points is a dictionary that links products to order point.
        """
        product_obj = Pool().get('product.product')

        res_dates = {}
        res_qties = {}

        min_quantities = {}
        for product_id in product_ids:
            order_point = order_points.get((location_id, product_id))
            if order_point:
                min_quantities[product_id] = order_point.min_quantity
            else:
                min_quantities[product_id] = 0.0

        current_date = min_date
        current_qties = min_date_qties.copy()
        while (current_date < max_date) or (current_date == min_date):
            for product_id in product_ids:
                current_qty = current_qties[product_id]
                min_quantity = min_quantities[product_id]
                res_qty = res_qties.get(product_id)
                res_date = res_dates.get(product_id)
                if current_qty < min_quantity:
                    if not res_date:
                        res_dates[product_id] = current_date
                    if (not res_qty) or (current_qty < res_qty):
                        res_qties[product_id] = current_qty

            with Transaction().set_context(stock_date_start=current_date,
                    stock_date_end=current_date):
                pbl = product_obj.products_by_location([location_id],
                    product_ids, with_childs=True, skip_zero=False)
            for key, qty in pbl.iteritems():
                _, product_id = key
                current_qties[product_id] += qty
            if current_date == datetime.date.max:
                break
            current_date += datetime.timedelta(1)

        return dict((x, (res_dates.get(x), res_qties.get(x)))
            for x in product_ids)

    def create(self, vals):
        for field_name in ('product', 'quantity', 'uom', 'company'):
            if not vals.get(field_name):
                self.raise_user_error('create_request')
        return super(PurchaseRequest, self).create(vals)

PurchaseRequest()


class CreatePurchaseRequestStart(ModelView):
    'Create Purchase Request'
    _name = 'purchase.request.create.start'
    _description = __doc__

CreatePurchaseRequestStart()


class CreatePurchaseRequest(Wizard):
    'Create Purchase Request'
    _name = 'purchase.request.create'

    start = StateView('purchase.request.create.start',
        'stock_supply.purchase_request_create_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('stock_supply.act_purchase_request_form_draft')

    def do_create_(self, session, action):
        purchase_request_obj = Pool().get('purchase.request')
        purchase_request_obj.generate_requests()
        return action, {}

    def transition_create_(self, session):
        return 'end'

CreatePurchaseRequest()


class CreatePurchaseAskTerm(ModelView):
    'Create Purchase Ask Term'
    _name = 'purchase.request.create_purchase.ask_term'
    _description = __doc__
    party = fields.Many2One('party.party', 'Supplier', readonly=True)
    company = fields.Many2One('company.company', 'Company', readonly=True)
    payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Payment Term', required=True)

CreatePurchaseAskTerm()


class CreatePurchaseAskParty(ModelView):
    'Create Purchase Ask Party'
    _name = 'purchase.request.create_purchase.ask_party'
    _description = __doc__
    product = fields.Many2One('product.product', 'Product', readonly=True)
    company = fields.Many2One('company.company', 'Company', readonly=True)
    party = fields.Many2One('party.party', 'Supplier', required=True)

CreatePurchaseAskParty()


class CreatePurchase(Wizard):
    'Create Purchase'
    _name = 'purchase.request.create_purchase'

    start = StateTransition()
    ask_party = StateView('purchase.request.create_purchase.ask_party',
        'stock_supply.purchase_request_create_purchase_ask_party', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'start', 'tryton-go-next', default=True),
            ])
    ask_term = StateView('purchase.request.create_purchase.ask_term',
        'stock_supply.purchase_request_create_purchase_ask_term_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'start', 'tryton-go-next', default=True),
            ])

    def __init__(self):
        super(CreatePurchase, self).__init__()
        self._error_messages.update({
            'missing_price': 'Purchase price is missing for product: %s ' \
                '(id: %s)!',
            'please_update': 'This price is necessary for creating purchase.'
            })

    def default_ask_party(self, session, fields):
        request_obj = Pool().get('purchase.request')
        requests = request_obj.browse(Transaction().context['active_ids'])
        for request in requests:
            if request.purchase_line:
                continue
            if not request.party:
                return {
                    'product': request.product.id,
                    'company': request.company.id,
                    }
        return {
            'product': request.product.id,
            'company': request.company.id,
            }

    def default_ask_term(self, session, fields):
        request_obj = Pool().get('purchase.request')
        requests = request_obj.browse(Transaction().context['active_ids'])
        for request in requests:
            if (not request.party) or request.purchase_line:
                continue
            if not request.party.supplier_payment_term:
                return {
                    'party': request.party.id,
                    'company': request.company.id,
                    }
        return {
            'party': request.party.id,
            'company': request.company.id,
            }

    def _group_purchase_key(self, requests, request):
        '''
        The key to group lines by purchases

        :param requests: a list of requests
        :param request: the request

        :return: a list of key-value as tuples of the purchase
        '''
        party_obj = Pool().get('party.party')

        return (
            ('company', request.company.id),
            ('party', request.party.id),
            ('payment_term', request.party.supplier_payment_term.id),
            ('warehouse', request.warehouse.id),
            # XXX use function field
            ('currency', request.company.currency.id),
            ('invoice_address', party_obj.address_get(request.party.id,
                    type='invoice')),
            )

    def transition_start(self, session):
        pool = Pool()
        request_obj = pool.get('purchase.request')
        party_obj = pool.get('party.party')
        purchase_obj = pool.get('purchase.purchase')
        line_obj = pool.get('purchase.line')
        date_obj = pool.get('ir.date')

        request_ids = Transaction().context['active_ids']

        if (session.ask_party.product
                and session.ask_party.party
                and session.ask_party.company):
            req_ids = request_obj.search([
                    ('id', 'in', request_ids),
                    ('party', '=', None),
                    ])
            if req_ids:
                request_obj.write(req_ids, {
                        'party': session.ask_party.party.id,
                        })
            session.ask_party.product = None
            session.ask_party.party = None
            session.ask_party.company = None
        elif (session.ask_term.payment_term
                and session.ask_term.party
                and session.ask_term.company):
            with Transaction().set_context(
                    company=session.ask_term.company.id):
                party_obj.write(session.ask_term.party.id, {
                        'supplier_payment_term': \
                            session.ask_term.payment_term.id,
                        })
            session.ask_term.payment_term = None
            session.ask_term.party = None
            session.ask_term.company = None

        req_ids = request_obj.search([
                ('id', 'in', request_ids),
                ('purchase_line', '=', None),
                ('party', '=', None),
                ])
        if req_ids:
            return 'ask_party'

        today = date_obj.today()
        requests = request_obj.browse(request_ids)

        requests = [r for r in requests if not r.purchase_line]
        if any(r for r in requests if not r.party.supplier_payment_term):
            return 'ask_term'

        keyfunc = partial(self._group_purchase_key, requests)
        requests = sorted(requests, key=keyfunc)

        with Transaction().set_user(0, set_context=True):
            for key, grouped_requests in groupby(requests, key=keyfunc):
                grouped_requests = list(grouped_requests)
                try:
                    purchase_date = min(r.purchase_date
                        for r in grouped_requests
                        if r.purchase_date)
                except ValueError:
                    purchase_date = today
                if purchase_date < today:
                    purchase_date = today
                values = {
                    'purchase_date': purchase_date,
                    }
                values.update(dict(key))
                purchase_id = purchase_obj.create(values)
                for request in grouped_requests:
                    values = self.compute_purchase_line(request)
                    values['purchase'] = purchase_id
                    line_id = line_obj.create(values)
                    request_obj.write(request.id, {
                            'purchase_line': line_id,
                            })
        return 'end'

    def _get_tax_rule_pattern(self, request):
        '''
        Get tax rule pattern

        :param request: the BrowseRecord of the purchase request
        :return: a dictionary to use as pattern for tax rule
        '''
        res = {}
        return res

    def compute_purchase_line(self, request):
        pool = Pool()
        product_obj = pool.get('product.product')
        tax_rule_obj = pool.get('account.tax.rule')
        line_obj = pool.get('purchase.line')

        line = {
            'product': request.product.id,
            'unit': request.uom.id,
            'quantity': request.quantity,
            'description': request.product.name,
            }

        # XXX purchase with several lines of the same product
        with Transaction().set_context(uom=request.uom.id,
                supplier=request.party.id,
                currency=request.company.currency.id):
            product_price = product_obj.get_purchase_price(
                    [request.product.id], request.quantity)[request.product.id]
            product_price = product_price.quantize(
                Decimal(1) / 10 ** line_obj.unit_price.digits[1])

        if not product_price:
            self.raise_user_error('missing_price', (request.product.name,
                    request.product.id), 'please_update')
        line['unit_price'] = product_price

        taxes = []
        for tax in request.product.supplier_taxes_used:
            if request.party and request.party.supplier_tax_rule:
                pattern = self._get_tax_rule_pattern(request)
                tax_id = tax_rule_obj.apply(request.party.supplier_tax_rule,
                        tax, pattern)
                if tax_id:
                    taxes.append(tax_id)
                continue
            taxes.append(tax.id)
        line['taxes'] = [('add', taxes)]
        return line

CreatePurchase()
