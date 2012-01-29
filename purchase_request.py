#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import operator
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.pyson import If, In, Eval, Get
from trytond.transaction import Transaction
from trytond.pool import Pool


class PurchaseRequest(ModelSQL, ModelView):
    'Purchase Request'
    _name = 'purchase.request'
    _description = __doc__

    product = fields.Many2One(
        'product.product', 'Product', required=True, select=1, readonly=True,
        domain=[('purchasable', '=', True)])
    party = fields.Many2One('party.party', 'Party',  select=1)
    quantity = fields.Float('Quantity', required=True)
    uom = fields.Many2One('product.uom', 'UOM', required=True, select=1)
    computed_quantity = fields.Float('Computed Quantity', readonly=True)
    computed_uom = fields.Many2One('product.uom', 'Computed UOM', readonly=True)
    purchase_date = fields.Date('Best Purchase Date', readonly=True)
    supply_date = fields.Date('Expected Supply Date', readonly=True)
    stock_level =  fields.Float('Stock at Supply Date', readonly=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[('type', '=', 'warehouse')], readonly=True)
    purchase_line = fields.Many2One(
        'purchase.line', 'Purchase Line',readonly=True)
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
            'create_request': 'Purchase requests are only created by the system.',
            })

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
            res[pr.id] = "%s@%s" % (pr.product.name, pr.warehouse.name)
        return res

    def search_rec_name(self, name, clause):
        res = []
        names = clause[2].split('@', 1)
        res.append(('product.template.name', clause[1], names[0]))
        if len(names) != 1 and names[1]:
            res.append(('warehouse', clause[1], names[1]))
        return res

    def default_company(self):
        return Transaction().context.get('company') or False

    def get_purchase(self, ids, name):
        res = {}

        requests = self.browse(ids)
        for request in requests:
            if request.purchase_line:
                res[request.id] = request.purchase_line.purchase.id
            else:
                res[request.id] = False
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
        purchase_request_obj = pool.get('purchase.request')
        product_obj = pool.get('product.product')
        location_obj = pool.get('stock.location')
        user_obj = pool.get('res.user')
        company = user_obj.browse(Transaction().user).company

        # fetch warehouses:
        warehouse_ids = location_obj.search([
            ('type','=','warehouse'),
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

        # fetch stockable products
        product_ids = product_obj.search([
            ('type', '=', 'stockable'), 
            ('purchasable', '=', True),
            ])
        #aggregate product by minimum supply date
        date2products = {}
        for product in product_obj.browse(product_ids):
            min_date, max_date = self.get_supply_dates(product)
            date2products.setdefault(min_date, []).append((product, max_date))

        # compute requests
        new_requests = []
        for min_date in date2products:
            product_ids = [x[0].id for x in date2products[min_date]]
            with Transaction().set_context(forecast=True,
                    stock_date_end=min_date or datetime.date.max):
                pbl = product_obj.products_by_location(warehouse_ids,
                    product_ids, with_childs=True, skip_zero=False)
            for product, max_date in date2products[min_date]:
                for warehouse_id in warehouse_ids:
                    qty = pbl.pop((warehouse_id, product.id))
                    order_point = product2ops.get((warehouse_id, product.id))
                    # Search for shortage between min-max
                    shortage_date, product_quantity = self.get_shortage(
                        warehouse_id, product.id, min_date, max_date,
                        min_date_qty=qty, order_point=order_point)

                    if shortage_date == None or product_quantity == None:
                        continue
                    # generate request values
                    request_val = self.compute_request(product, warehouse_id,
                        shortage_date, product_quantity, company, order_point)
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
                new_req.update({'product': new_req['product'].id,
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
        product_supplier_obj = pool.get('purchase.product_supplier')
        req_ids = request_obj.search([
            ('purchase_line', '=', False),
            ('origin', 'like', 'stock.order_point,%'),
            ])
        request_obj.delete(req_ids)

        req_ids = request_obj.search([
                ('purchase_line.moves', '=', False),
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
                []).append({'supply_date': request.supply_date or datetime.date.max,
                            'quantity': quantity,
                            'uom': uom}
                           )

        for i in existing_req.itervalues():
            i.sort(lambda r,s: cmp(r['supply_date'],s['supply_date']))

        # Update new requests to take existing requests into account
        new_requests.sort(key=operator.itemgetter('supply_date'))
        for new_req in new_requests:
            for old_req in existing_req.get((new_req['product'].id,
                                             new_req['warehouse']), []):
                if old_req['supply_date'] <= new_req['supply_date']:
                    quantity = uom_obj.compute_qty(old_req['uom'],
                            old_req['quantity'], new_req['uom'])
                    new_req['quantity'] = max(0.0, new_req['quantity'] - quantity)
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
            supply_date, next_supply_date = product_supplier_obj.\
                    compute_supply_date(product_supplier, date=today)
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
                    product_supplier, date=today)[0]
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
            origin = 'stock.order_point,%s'%order_point.id
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

    def get_shortage(self, location_id, product_id, min_date,
                     max_date, min_date_qty, order_point=None):
        """
        Return between min_date and max_date  the first date where the
            stock quantity is less than the minimal quantity and
            the smallest stock quantity in the interval
            or None if there is no date where stock quantity is less than
            the minimal quantity
        The minimal quantity comes from the order_point or is zero

        :param location_id: the stock location id
        :param produc_id: the product id
        :param min_date: the minimal date
        :param max_date: the maximal date
        :param min_date_qty: the stock quantity at the minimal date
        :param order_point: a BrowseRecord of the Order Point
        :return: a tuple with the date and the quantity
        """
        product_obj = Pool().get('product.product')

        res_date = None
        res_qty = None

        min_quantity = order_point and order_point.min_quantity or 0.0

        current_date = min_date
        current_qty = min_date_qty
        while (current_date < max_date) or (current_date == min_date):
            if current_qty < min_quantity:
                if not res_date:
                    res_date = current_date
                if (not res_qty) or (current_qty < res_qty):
                    res_qty = current_qty

            with Transaction().set_context(stock_date_start=current_date,
                    stock_date_end=current_date):
                res = product_obj.products_by_location([location_id],
                [product_id], with_childs=True, skip_zero=False)
            for qty in res.itervalues():
                current_qty += qty
            if current_date == datetime.date.max:
                break
            current_date += datetime.timedelta(1)

        return (res_date, res_qty)

    def create(self, vals):
        for field_name in ('product', 'quantity', 'uom', 'warehouse', 'company'):
            if not vals.get(field_name):
                self.raise_user_error('create_request')
        return super(PurchaseRequest, self).create(vals)

PurchaseRequest()


class CreatePurchaseRequestInit(ModelView):
    'Create Purchase Request Init'
    _name = 'purchase.request.create_purchase_request.init'
    _description = __doc__

CreatePurchaseRequestInit()


class CreatePurchaseRequest(Wizard):
    'Create Purchase Request'
    _name = 'purchase.request.create_purchase_request'

    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'purchase.request.create_purchase_request.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('create', 'Create', 'tryton-ok', True),
                    ],
                },
            },
        'create': {
            'actions': ['_create_purchase_request'],
            'result': {
                'type': 'action',
                'action': '_open',
                'state': 'end',
                },
            },
        }

    def _create_purchase_request(self, data):
        purchase_request_obj = Pool().get('purchase.request')
        purchase_request_obj.generate_requests()
        return {}

    def _open(self, data):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        act_window_obj = pool.get('ir.action.act_window')
        act_window_id = model_data_obj.get_id('stock_supply',
            'act_purchase_request_form_draft')
        return act_window_obj.read(act_window_id)

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

    states = {

        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_create_purchase',
                },
            },


        'ask_user_party': {
            'actions': ['_set_default_party'],
            'result': {
                'type': 'form',
                'object': 'purchase.request.create_purchase.ask_party',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('init', 'Continue', 'tryton-go-next', True),
                    ],
                },
            },

        'ask_user_term': {
            'actions': ['_set_default_term'],
            'result': {
                'type': 'form',
                'object': 'purchase.request.create_purchase.ask_term',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('init', 'Continue', 'tryton-go-next', True),
                    ],
                },
            },

        }

    def __init__(self):
        super(CreatePurchase, self).__init__()
        self._error_messages.update({
            'missing_price': 'Purchase price is missing for product: %s (id: %s)!',
            'please_update': 'This price is necessary for creating purchase.'
            })

    def _set_default_party(self, data):

        request_obj = Pool().get('purchase.request')
        requests = request_obj.browse(data['ids'])
        for request in requests:
            if request.purchase_line:
                continue
            if not request.party:
                return {'product': request.product.id,'company': request.company.id}

        return {'product': request.product.id,'company': request.company.id}

    def _set_default_term(self, data):

        request_obj = Pool().get('purchase.request')
        requests = request_obj.browse(data['ids'])
        for request in requests:
            if (not request.party) or request.purchase_line:
                continue
            if not request.party.supplier_payment_term:
                return {'party': request.party.id,'company': request.company.id}

        return {'party': request.party.id,'company': request.company.id}

    def _create_purchase(self, data):
        pool = Pool()
        request_obj = pool.get('purchase.request')
        party_obj = pool.get('party.party')
        purchase_obj = pool.get('purchase.purchase')
        product_obj = pool.get('product.product')
        line_obj = pool.get('purchase.line')
        date_obj = pool.get('ir.date')

        form = data['form']
        if form.get('product') and form.get('party') and \
                form.get('company'):
            req_ids = request_obj.search([
                ('id', 'in', data['ids']),
                ('party', '=', False),
                ])
            if req_ids:
                request_obj.write(req_ids, {'party': form['party']})

        elif form.get('payment_term') and form.get('party') and \
                form.get('company'):
            with Transaction().set_context(company=form['company']):
                party_obj.write(form['party'],{
                    'supplier_payment_term': form['payment_term']
                    })

        req_ids = request_obj.search([
            ('id', 'in', data['ids']),
            ('purchase_line', '=', False),
            ('party', '=', False),
            ])
        if req_ids:
            return 'ask_user_party'

        today = date_obj.today()
        requests = request_obj.browse(data['ids'])
        purchases = {}
        # collect data
        for request in requests:
            if request.purchase_line:
                continue

            if not request.party.supplier_payment_term:
                return 'ask_user_term'

            key = (request.party.id, request.company.id, request.warehouse.id)
            if key not in purchases:
                if request.purchase_date and request.purchase_date >= today:
                    purchase_date = request.purchase_date
                else:
                    purchase_date = today
                purchase = {
                    'company': request.company.id,
                    'party': request.party.id,
                    'purchase_date': purchase_date,
                    'payment_term': request.party.supplier_payment_term.id,
                    'warehouse': request.warehouse.id,
                    'currency': request.company.currency.id,
                    'invoice_address': party_obj.address_get(request.party.id,
                            type='invoice'),
                    'lines': [],
                    }

                purchases[key] = purchase
            else:
                purchase = purchases[key]

            line = self.compute_purchase_line(request)
            purchase['lines'].append(line)
            if request.purchase_date:
                if purchase.get('purchase_date'):
                    purchase['purchase_date'] = min(purchase['purchase_date'],
                                                    request.purchase_date)
                else:
                    purchase['purchase_date'] = request.purchase_date

        # Create all
        for purchase in purchases.itervalues():
            lines = purchase.pop('lines')
            with Transaction().set_user(0, set_context=True):
                purchase_id = purchase_obj.create(purchase)
            for line in lines:
                request_id = line.pop('request')
                line['purchase'] = purchase_id
                with Transaction().set_user(0):
                    line_id = line_obj.create(line)
                request_obj.write(request_id, {'purchase_line': line_id})

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
        party_obj = pool.get('party.party')
        product_obj = pool.get('product.product')
        tax_rule_obj = pool.get('account.tax.rule')
        line_obj = pool.get('purchase.line')

        line = {
            'product': request.product.id,
            'unit': request.uom.id,
            'quantity': request.quantity,
            'request': request.id,
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
