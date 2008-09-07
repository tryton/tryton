#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
import datetime

# TODO ensure that the link p_request p_line is never inconsistent
# (uom, qty, product, ...).
class PurchaseRequest(OSV):
    'Purchase Request'
    _name = 'stock.purchase_request'
    _description = __doc__

    product = fields.Many2One(
        'product.product', 'Product', required=True, select=True)
    party = fields.Many2One('relationship.party', 'Party',  select=True)
    quantity = fields.Float('Quantity', required=True)
    uom = fields.Many2One('product.uom', 'UOM', required=True, select=True)
    purchase_date = fields.Date('Expected Purchase Date')
    supply_date = fields.Date('Expected Suplly Date')
    stock_level =  fields.Float('Stock at Supply Date')
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain="[('type', '=', 'warehouse')]")
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line')
    company = fields.Many2One('company.company', 'Company', required=True)

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

PurchaseRequest()


class CreatePurchaseAsk(WizardOSV):
    _name = 'stock.purchase_request.create_purchase.ask'
    party = fields.Many2One('relationship.party', 'Supplier', readonly=True)
    company = fields.Many2One('company.company', 'Company', readonly=True)
    payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Payment Term', required=True)

CreatePurchaseAsk()

class CreatePurchase(Wizard):
    'Create Purchase'
    _name = 'stock.purchase_request.create_purchase'

    states = {

        'init': {
            'result': {
                'type': 'action',
                'action': '_compute_purchase',
                'state': 'choice',
                },
            },

        'choice': {
            'result': {
                'type': 'choice',
                'next_state': '_check_payment_term',
                },
            },

        'ask_user': {
            'actions': ['_set_default'],
            'result': {
                'type': 'form',
                'object': 'stock.purchase_request.create_purchase.ask',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('choice', 'Continue', 'tryton-ok', True),
                    ],
                },
            },

        'create': {
            'result': {
                'type': 'action',
                'action': '_create_purchase',
                'state': 'end',
                },
            },

        }

    def _set_default(self, cursor, user, data, context=None):

        if not data.get('party_wo_pt'):
            return {}
        party, company = data['party_wo_pt'].pop()
        return {'party': party,'company': company}

    def _check_payment_term(self, cursor, user, data, context=None):
        party_obj = self.pool.get('relationship.party')
        if 'purchases' not in data:
            return 'end'
        form = data['form']
        if form.get('payment_term') and form.get('party') and \
                form.get('company'):
            for key, val in data['purchases'].iteritems():
                if (key[0], key[1]) == (form['party'],
                                        form['company']):
                    val['payment_term'] = form['payment_term']
            local_context = context.copy()
            local_context['company'] = form['company']
            party_obj.write(
                cursor, user, form['party'],
                {'supplier_payment_term': form['payment_term']}, context=local_context)
        if data.get('party_wo_pt'):
            return 'ask_user'
        return 'create'

    def _compute_purchase(self, cursor, user, data, context=None):
        request_obj = self.pool.get('stock.purchase_request')
        requests = request_obj.browse(cursor, user, data['ids'], context=context)
        purchases = {}
        for request in requests:
            if (not request.party) or request.purchase_line:
                continue
            key = (request.party.id, request.company.id, request.warehouse.id)

            if key not in purchases:
                purchase = {
                    'company': request.company.id,
                    'party': request.party.id,
                    'purchase_date': request.purchase_date or datetime.date.today(),
                    'payment_term': request.party.supplier_payment_term and \
                        request.party.supplier_payment_term.id or None,
                    'warehouse': request.warehouse.id,
                    'currency': request.company.currency.id,
                    'lines': [],
                    }
                purchases[key] = purchase
            else:
                purchase = purchases[key]

            purchase['lines'].append({
                'product': request.product.id,
                'unit': request.uom.id,
                'quantity': request.quantity,
                'request': request.id,
                })
            if request.purchase_date:
                if not purchase['purchase_date']:
                    purchase['purchase_date'] = request.purchase_date
                else:
                    purchase['purchase_date'] = min(purchase['purchase_date'],
                                                    request.purchase_date)
            data['purchases'] = purchases
            data['party_wo_pt'] = set(
                k[:2] for k in purchases if not purchases[k]['payment_term'])
        return {}

    def _create_purchase(self, cursor, user, data, context=None):
        request_obj = self.pool.get('stock.purchase_request')
        purchase_obj = self.pool.get('purchase.purchase')
        line_obj = self.pool.get('purchase.line')
        product_obj = self.pool.get('product.product')
        created_ids = []
        products = []
        # collect  product names
        for purchase in data['purchases'].itervalues():
            for line in purchase['lines']:
                products.append(line['product'])
        product_name = product_obj.name_get(
            cursor, user, products, context=context)

        # create purchases, lines and update requests
        for purchase in data['purchases'].itervalues():
            purchase_lines = purchase.pop('lines')
            purchase_id = purchase_obj.create(
                cursor, user, purchase, context=context)
            created_ids.append(purchase_id)
            for line in purchase_lines:
                request_id = line.pop('request')
                line['purchase'] = purchase_id
                line['description'] = product_name[line['product']][1]
                local_context = context.copy()
                local_context['uom'] = line['unit']
                local_context['supplier'] = purchase['party']
                local_context['currency'] = purchase['currency']
                product_price = product_obj.get_purchase_price(
                    cursor, user, [line['product']], line['quantity'],
                    context=local_context)[line['product']]
                line['unit_price'] = product_price
                line_id = line_obj.create(cursor, user, line, context=context)
                request_obj.write(
                    cursor, user, request_id, {'purchase_line': line_id},
                    context=context)

        return {}

CreatePurchase()
