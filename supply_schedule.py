from trytond.wizard import Wizard, WizardOSV
import datetime
# * Generate for X day in advance ?
# * Provide a way to choose how mutch day before the shortage the suplly
#   must be planned

class GeneratePurchaseRequest(Wizard):
    'Generate Purchase Requests'
    _name = 'stock.generate_purchase_request'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': 'generate_requests',
                'state': 'end',
            },
        },
    }


    def generate_requests(self, cursor, user, data, context=None):
        """
        For each order point compute the purchase that must be create
        today to meet product outputs.
        """
        order_point_obj = self.pool.get('stock.order_point')
        purchase_request_obj = self.pool.get('stock.purchase_request')
        product_obj = self.pool.get('product.product')
        order_point_ids = order_point_obj.search(
            cursor, user, [], context=context)
        order_points = order_point_obj.browse( #XXX filter on company ??
            cursor, user, order_point_ids, context=context)

        product_ids = [op.product.id for op in order_points]
        products = product_obj.browse(cursor, user, product_ids, context=context)
        local_context = context.copy()
        new_requests = []


        for product in products:
            # Get min and max supply dates
            min_date, max_date = self.get_supply_dates(
                cursor, user, product, context=context)
            # Fetch all locations for whose this product has an order point
            locations = [op.location.id for op in product.order_points]
            # Compute stock
            local_context.update({'stock_date_end': min_date or datetime.date.max})
            pbl = product_obj.products_by_location(
                cursor, user, locations, [product.id], with_childs=True,
                skip_zero=False, context=local_context)

            for order_point in product.order_points:
                # ignore order point on other locations than warehouse
                if order_point.location.type != 'warehouse':
                    continue
                # Search for shortage between min-max
                shortage_date, stock_quantity = self.get_shortage(
                    cursor, user, order_point, min_date, max_date,
                    min_date_stock=pbl[order_point.location.id, product.id],
                    context=context)

                if shortage_date == None or stock_quantity == None:
                    continue
                request_val = self.compute_request(
                    cursor, user, order_point, shortage_date,
                    stock_quantity, context=context)

                new_requests.append(request_val)
        self.create_requests(cursor, user, new_requests, context=context)
        return {}

    def create_requests(self, cursor, user, new_requests, context=None):
        """
        Compare new_requests with already existing request and avoid
        to re-create existing requests.
        """
        # delete purchase request without a purchase line
        uom_obj = self.pool.get('product.uom')
        request_obj = self.pool.get('stock.purchase_request')
        product_supplier_obj = self.pool.get('purchase.product_supplier')
        req_ids = request_obj.search(
            cursor, user, [('purchase_line', '=', False)], context=context)
        request_obj.delete(cursor, user, req_ids, context=context)

        req_ids = request_obj.search(cursor, user, [], context=context)
        requests = request_obj.browse(cursor, user, req_ids, context=context)
        # Fetch delivery_times for each (product,supplier)
        sup_delivery_time = {}
        for request in requests:
            product, supplier = None, None
            if request.purchase_line:
                product = request.purchase_line.product.id
                supplier = request.purchase_line.purchase.party.id
            else:
                product = request.product.id
                supplier = request.party and request.party.id
            if not supplier:
                continue
            sup_delivery_time[product, supplier] = None

        prod_sup_ids = product_supplier_obj.search(
            cursor, user,
            ['OR', ] + [
                ['AND', ('product', '=', x[0]), ('party', '=', x[1])] \
                    for x in sup_delivery_time.iterkeys()
                ],
            context=context)
        for prod_sup in product_supplier_obj.browse(cursor, user, prod_sup_ids,
                                                    context=context):
            sup_delivery_time[prod_sup.product.id, prod_sup.party.id] = \
                prod_sup.delivery_time

        # Fetch data from existing requests
        existing_req = {}
        for request in requests:
            if request.purchase_line:
                product = request.purchase_line.product
                warehouse = request.purchase_line.purchase.warehouse
                purchase_date = request.purchase_line.purchase.purchase_date
                qty = line.quantity
                uom = line.unit
                supplier = line.purchase.party
            else:
                product = request.product
                warehouse = request.warehouse
                purchase_date = request.purchase_date
                qty = request.quantity
                uom = request.uom
                supplier = request.party.id

            delivery_time = sup_delivery_time.get((product.id, supplier.id))
            if delivery_time:
                supply_date = purchase_date + \
                    datetime.timedelta(delivery_time)
            else:
                supply_date = datetime.date.max

            existing_req.setdefault((product.id, warehouse.id), []).append(
                {'supply_date': supply_date, 'quantity': qty, 'uom': uom})

        for i in existing_req.itervalues():
            i.sort

        # Update new requests to take existing requests into account
        new_requests.sort(lambda r,s: cmp(r['supply_date'],s['supply_date']))
        for new_req in new_requests:
            for old_req in existing_req.get((new_req['product'].id,
                                             new_req['warehouse'].id), []):
                if old_req['supply_date'] <= new_req['supply_date']:
                    quantity = uom_obj.compute_qty(
                        cursor, user, old_req['uom'], old_req['quantity'],
                        new_req['uom'], context=context)
                    new_req['quantity'] = max(0.0, new_req['quantity'] - quantity)
                    old_req['quantity'] = uom_obj.compute_qty(
                        cursor, user, new_req['uom'],
                        max(0.0, quantity - new_req['quantity']),
                        old_req['uom'], context=context)
                else:
                    break

        for new_req in new_requests:
            if new_req['quantity'] > 0.0:
                new_req.update({'product': new_req['product'].id,
                                'party': new_req['party'] and new_req['party'].id,
                                'uom': new_req['uom'].id,
                                'company': new_req['company'].id
                                })
                request_obj.create(cursor, user, new_req, context=context)

    def get_supply_dates(self, cursor, user, product, context=None):
        """
        Return for the given product min and max values for the
        earliest supply dates across all available suppliers.
        """
        min_date = None
        max_date = None
        today = datetime.date.today()

        for product_supplier in product.product_suppliers:
            supply_date = today + datetime.timedelta(product_supplier.delivery_time)
            if (not min_date) or supply_date < min_date:
                min_date = supply_date
            if (not max_date) or supply_date > max_date:
                max_date = supply_date
        return (min_date, max_date)

    def compute_request(self, cursor, user, order_point, shortage_date,
                        stock_quantity, context=None):
        """
        Return the value of the purchase request which will answer to
        the needed quantity at the given date. I.e: the latest
        purchase date, the expected supply date and the prefered
        supplier.
        """
        product = order_point.product
        supplier = None
        seq = None
        on_time = False
        today = datetime.date.today()

        for product_supplier in product.product_suppliers:
            supply_date = today + datetime.timedelta(product_supplier.delivery_time)
            sup_on_time = supply_date < shortage_date
            if not supplier:
                supplier = product_supplier.party
                on_time = sup_on_time
                seq = product_supplier.sequence
                continue

            if (sup_on_time, product_supplier.sequence) < (on_time, seq):
                supplier = product_supplier.party
                on_time = sup_on_time
                seq = product_supplier.sequence

        if supplier and product_supplier.delivery_time:
            purchase_date = \
                shortage_date - datetime.timedelta(product_supplier.delivery_time)
        else:
            purchase_date = today

        return {'product': product,
                'party': supplier and supplier or None,
                'quantity': order_point.max_quantity - stock_quantity,
                'uom': product.default_uom,
                'purchase_date': purchase_date,
                'supply_date': shortage_date,
                'stock_level': stock_quantity,
                'company': order_point.company,
                'warehouse': order_point.location,
                }

    def get_shortage(self, cursor, user, order_point, min_date,
                     max_date, min_date_stock, context=None):
        """
        Compute stock quantities between the two given dates. If given
        the order point, one date will be lacking in products this
        date is returned alongside the stock level at this date.

        If no dates are given, the stock is computed for an infinire
        date and the shortage date is today.
        """
        product_obj = self.pool.get('product.product')

        if not min_date:
            if min_date_stock < order_point.min_quantity:
                return (
                    datetime.date.today(), min_date_stock)
            else:
                return (None, None)
        if not max_date: max_date = min_date

        current_date = min_date
        current_stock = min_date_stock
        while current_date <= max_date:
            if current_stock < order_point.min_quantity:
                return current_date, current_stock

            local_context = context.copy()
            local_context['stock_date_start'] = current_date
            local_context['stock_date_end'] = current_date

            res = product_obj.products_by_location(
                cursor, user, [order_point.location.id],
                [order_point.location.id], with_childs=True, skip_zero=False,
                context=context)
            for qty in res.itervalues():
                current_stock += qty
            current_date += datetime.timedelta(1)

        return (None, None)

GeneratePurchaseRequest()
