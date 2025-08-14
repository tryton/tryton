# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal
from itertools import zip_longest

import dateutil
import shopify

from trytond.i18n import gettext
from trytond.model import ModelView, Unique, fields
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import round_price
from trytond.modules.sale.exceptions import SaleConfirmError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from . import graphql
from .common import IdentifierMixin, gid2id, id2gid, setattr_changed
from .exceptions import ShopifyError
from .shopify_retry import GraphQLException

QUERY_ORDER = '''\
query GetOrder($id: ID!) {
    order(id: $id) %(fields)s
}'''

QUERY_ORDER_CURSOR = '''\
query GetOrder($id: ID!, $cursor: String) {
    order(id: $id) %(fields)s
}'''

QUERY_ORDER_CLOSED = '''\
query GetOrderClosed($id: ID!) {
    order(id: $id) {
        closed
    }
}'''

QUERY_ORDER_FULFILLABLE_QUANTITIES = '''\
query GetOrderFulfillableQuantities($id: ID!, $cursor: String) {
    order(id: $id) {
        lineItems(first: 250, after: $cursor) {
            nodes {
                id
                fulfillableQuantity
            }
            pageInfo {
                hasNextPage
                endCursor
            }
        }
    }
}'''

QUERY_ORDER_SUGGESTED_REFUND = '''\
query GetOrderSuggestedRefund(
        $id: ID!,
        $refundShipping: Boolean,
        $refundLineItems: [RefundLineItemInput!]) {
    order(id: $id) {
        suggestedRefund(
                refundShipping: $refundShipping,
                refundLineItems: $refundLineItems) {
            suggestedTransactions {
                amountSet {
                    presentmentMoney {
                        amount
                        currencyCode
                    }
                }
                gateway
                kind
                parentTransaction {
                    id
                }
            }
        }
    }
}'''


MUTATION_ORDER_CLOSE = '''\
mutation OrderClose($input: OrderCloseInput!) {
    orderClose(input: $input) {
        userErrors {
            field
            message
        }
    }
}'''

MUTATION_ORDER_OPEN = '''\
mutation OrderOpen($input: OrderOpenInput!) {
    orderOpen(input: $input) {
        userErrors {
            field
            message
        }
    }
}'''


QUERY_FULFILLMENT_ORDER = '''\
query GetFulfillmentOrder($id: ID!, $cursor: String) {
    fulfillmentOrder(id: $id) %(fields)s
}'''


MUTATION_FULFILLMENT_CREATE = '''\
mutation fulfillmentCreate($fulfillment: FulfillmentInput!) {
    fulfillmentCreate(fulfillment: $fulfillment) {
        fulfillment {
            id
        }
        userErrors {
            field
            message
        }
    }
}'''

MUTATION_FULFILLMENT_CANCEL = '''\
mutation fulfillmentCancel($id: ID!) {
    fulfillmentCancel(id: $id) {
        userErrors {
            field
            message
        }
    }
}'''

QUERY_REFUND_CURSOR = '''\
        query GetRefund($id: ID!, $cursor: String) {
    refund(id: $id) %(fields)s
}'''

MUTATION_REFUND_CREATE = '''\
mutation RefundCreate($input: RefundInput!) {
    refundCreate(input: $input) {
        userErrors {
            field
            message
        }
    }
}'''


class Sale(IdentifierMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'

    shopify_tax_adjustment = Monetary(
        "Shopify Tax Adjustment",
        currency='currency', digits='currency', readonly=True)
    shopify_status_url = fields.Char("Shopify Status URL", readonly=True)
    shopify_resource = 'orders'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('web_shop_shopify_identifier_unique',
                Unique(t, t.web_shop, t.shopify_identifier_signed),
                'web_shop_shopify.msg_identifier_sale_web_shop_unique'),
            ]

    def get_web_status_url(self, name):
        url = super().get_web_status_url(name)
        if self.shopify_status_url:
            url = self.shopify_status_url
        return url

    @fields.depends('shopify_tax_adjustment')
    def get_tax_amount(self):
        amount = super().get_tax_amount()
        if self.shopify_tax_adjustment:
            amount += self.shopify_tax_adjustment
        return amount

    @classmethod
    def shopify_fields(cls):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        Line = pool.get('sale.line')
        Payment = pool.get('account.payment')
        return {
            'id': None,
            'customer': Party.shopify_fields(),
            'presentmentCurrencyCode': None,
            'shippingAddress': Address.shopify_fields(),
            'billingAddress': Address.shopify_fields(),
            'name': None,
            'note': None,
            'processedAt': None,
            'createdAt': None,
            'phone': None,
            'refunds': {
                'id': None,
                'refundLineItems(first: 10)': {
                    'nodes': {
                        'lineItem': {
                            'id': None,
                            },
                        'restockType': None,
                        'quantity': None,
                        },
                    'pageInfo': {
                        'hasNextPage': None,
                        'endCursor': None,
                        },
                    },
                },
            'lineItems(first: 100)': {
                'nodes': Line.shopify_fields(),
                'pageInfo': {
                    'hasNextPage': None,
                    'endCursor': None,
                    },
                },
            'shippingLines(first: 10)': {
                'nodes': {
                    'title': None,
                    'currentDiscountedPriceSet': {
                        'presentmentMoney': {
                            'amount': None,
                            },
                        },
                    },
                'pageInfo': {
                    'hasNextPage': None,
                    'endCursor': None,
                    },
                },
            'fulfillmentOrders(first: 10)': {
                'nodes': {
                    'id': None,
                    'assignedLocation': {
                        'location': {
                            'id': None,
                            },
                        },
                    'lineItems(first: 100)': {
                        'nodes': {
                            'lineItem': {
                                'id': None,
                                },
                            'totalQuantity': None,
                            'remainingQuantity': None,
                            },
                        'pageInfo': {
                            'hasNextPage': None,
                            'endCursor': None,
                            },
                        },
                    },
                'pageInfo': {
                    'hasNextPage': None,
                    'endCursor': None,
                    }
                },
            'transactions': Payment.shopify_fields(),
            'totalPriceSet': {
                'presentmentMoney': {
                    'amount': None,
                    },
                },
            'currentTotalPriceSet': {
                'presentmentMoney': {
                    'amount': None,
                    },
                },
            'statusPageUrl': None,
            }

    @classmethod
    def get_from_shopify(cls, shop, order, sale=None):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        Currency = pool.get('currency.currency')
        Line = pool.get('sale.line')

        shopify_fields = cls.shopify_fields()

        if order.get('customer'):
            party = Party.get_from_shopify(shop, order['customer'])
            party.save()
            party.set_shopify_identifier(shop, gid2id(order['customer']['id']))
        else:
            party = shop.guest_party

        if not sale:
            sale = shop.get_sale(party=party)
            sale.web_id = str(gid2id(order['id']))
            sale.shopify_identifier = gid2id(order['id'])

            shopify_fulfillments = graphql.iterate(
                QUERY_ORDER_CURSOR % {
                    'fields': graphql.selection({
                            'fulfillmentOrders(first: 10, after: $cursor)': (
                                shopify_fields[
                                    'fulfillmentOrders(first: 10)']),
                            }),
                    },
                {'id': order['id']}, 'order',
                'fulfillmentOrders', order)
            location_ids = {
                str(gid2id(f['assignedLocation']['location']['id']))
                for f in shopify_fulfillments}
            for location_id in location_ids:
                for shop_warehouse in shop.shopify_warehouses:
                    if shop_warehouse.shopify_id == location_id:
                        sale.warehouse = shop_warehouse.warehouse
                        break
        setattr_changed(sale, 'party', party)

        assert sale.shopify_identifier == gid2id(order['id'])
        if sale.currency.code != order['presentmentCurrencyCode']:
            sale.currency, = Currency.search([
                    ('code', '=', order['presentmentCurrencyCode']),
                    ], limit=1)

        if sale.party != shop.guest_party:
            if order.get('shippingAddress'):
                shipment_address = party.get_address_from_shopify(
                    order['shippingAddress'])
            else:
                shipment_address = None
            if order.get('billingAddress'):
                invoice_address = party.get_address_from_shopify(
                    order['billingAddress'])
            else:
                invoice_address = None
        else:
            shipment_address = sale.party.address_get(type='delivery')
            invoice_address = sale.party.address_get(type='invoice')

        if shipment_address:
            setattr_changed(sale, 'shipment_address', shipment_address)
        if invoice_address or shipment_address:
            setattr_changed(
                sale, 'invoice_address', invoice_address or shipment_address)

        if not party.addresses:
            address = Address(party=party)
            address.save()
            if not sale.shipment_address:
                sale.shipment_address = address
            if not sale.invoice_address:
                sale.invoice_address = address

        setattr_changed(sale, 'reference', order['name'])
        setattr_changed(sale, 'shopify_status_url', order['statusPageUrl'])
        setattr_changed(sale, 'comment', order['note'])
        setattr_changed(sale, 'sale_date', dateutil.parser.isoparse(
                order['processedAt'] or order['createdAt']).date())

        if order['phone']:
            for contact_mechanism in party.contact_mechanisms:
                if (contact_mechanism.type in {'phone', 'mobile'}
                        and (contact_mechanism.value_compact
                            == contact_mechanism.format_value_compact(
                                order['phone'], contact_mechanism.type))):
                    break
            else:
                contact_mechanism = ContactMechanism(
                    party=party, type='phone', value=order['phone'])
            setattr_changed(sale, 'contact', contact_mechanism)

        refund_line_items = defaultdict(list)
        for refund in order['refunds']:
            shopify_refund_line_items = graphql.iterate(
                QUERY_REFUND_CURSOR % {
                    'fields': graphql.selection({
                            'refundLineItems(first: 10, after: $cursor)': (
                                shopify_fields['refunds'][
                                    'refundLineItems(first: 10)']),
                            }),
                    },
                {'id': refund['id']}, 'refund',
                'refundLineItems', refund)
            for refund_line_item in shopify_refund_line_items:
                line_item_id = gid2id(refund_line_item['lineItem']['id'])
                refund_line_items[line_item_id].append(refund_line_item)

        line2warehouses = defaultdict(set)
        shopify_fulfillment_orders = graphql.iterate(
            QUERY_ORDER_CURSOR % {
                'fields': graphql.selection({
                        'fulfillmentOrders(first: 10, after: $cursor)': (
                            shopify_fields[
                                'fulfillmentOrders(first: 10)']),
                        }),
                },
            {'id': order['id']}, 'order',
            'fulfillmentOrders', order)
        for fulfillment_order in shopify_fulfillment_orders:
            location_id = str(gid2id(
                fulfillment_order['assignedLocation']['location']['id']))
            for shop_warehouse in shop.shopify_warehouses:
                if shop_warehouse.shopify_id == location_id:
                    warehouse = shop_warehouse.warehouse
                    break
            else:
                continue
            shopify_line_items = graphql.iterate(
                QUERY_FULFILLMENT_ORDER % {
                    'fields': graphql.selection({
                            'lineItems(first: 100, after: $cursor)': (
                                shopify_fields[
                                    'fulfillmentOrders(first: 10)'][
                                    'nodes'][
                                    'lineItems(first: 100)']),
                            }),
                    },
                {'id': fulfillment_order['id']}, 'fulfillmentOrder',
                'lineItems', fulfillment_order)
            for line_item in shopify_line_items:
                if line_item['remainingQuantity']:
                    line2warehouses[gid2id(line_item['lineItem']['id'])].add(
                        warehouse)

        id2line = {
            l.shopify_identifier: l for l in getattr(sale, 'lines', [])
            if l.shopify_identifier}
        shipping_lines = [
            l for l in getattr(sale, 'lines', []) if not
            l.shopify_identifier]
        lines = []
        shopify_line_items = graphql.iterate(
            QUERY_ORDER_CURSOR % {
                'fields': graphql.selection({
                        'lineItems(first: 100, after: $cursor)': (
                            shopify_fields['lineItems(first: 100)']),
                        }),
                },
            {'id': order['id']}, 'order',
            'lineItems', order)
        for line_item in shopify_line_items:
            line_item_id = gid2id(line_item['id'])
            line = id2line.pop(line_item_id, None)
            warehouses = line2warehouses[line_item_id]
            warehouse = None
            if len(warehouses) == 1:
                warehouse = warehouses.pop()
            elif not warehouses:
                if line:
                    # keep existing warehouse
                    # if the line has already been shipped
                    # (no remaining quantity)
                    warehouse = line.shopify_warehouse
                if not warehouse:
                    warehouse = sale.warehouse
            quantity = line_item['quantity']
            for refund_line_item in refund_line_items[
                    gid2id(line_item['id'])]:
                quantity -= refund_line_item['quantity']
            lines.append(Line.get_from_shopify(
                    sale, line_item, quantity, warehouse=warehouse, line=line))
        shopify_shipping_lines = graphql.iterate(
            QUERY_ORDER_CURSOR % {
                'fields': graphql.selection({
                        'shippingLines(first: 10, after: $cursor)': (
                            shopify_fields['shippingLines(first: 10)']),
                        }),
                },
            {'id': order['id']}, 'order',
            'shippingLines', order)
        for shipping_line, line in zip_longest(
                shopify_shipping_lines, shipping_lines):
            if shipping_line:
                line = Line.get_from_shopify_shipping(
                    sale, shipping_line, line=line)
            else:
                line.quantity = 0
            lines.append(line)
        for line in id2line.values():
            line.quantity = 0
            lines.append(line)
        sale.lines = lines
        return sale

    @property
    def invoice_grouping_method(self):
        method = super().invoice_grouping_method
        if self.web_shop and self.web_shop.type == 'shopify':
            # Can not group in order to spread tax adjustment
            method = None
        return method

    def create_invoice(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        invoice = super().create_invoice()
        if invoice and self.shopify_tax_adjustment:
            invoice.save()
            adjustment = Currency.compute(
                self.currency, self.shopify_tax_adjustment, invoice.currency,
                round=False)
            untaxed_amount = Currency.compute(
                self.currency, self.untaxed_amount, invoice.currency,
                round=False)
            remaining = invoice.currency.round(
                adjustment * (invoice.untaxed_amount / untaxed_amount))
            taxes = invoice.taxes
            for tax in taxes:
                if tax.amount:
                    if invoice.tax_amount:
                        ratio = tax.amount / invoice.tax_amount
                    else:
                        ratio = 1 / len(invoice.taxes)
                    value = invoice.currency.round(adjustment * ratio)
                    tax.amount += value
                    remaining -= value
            if remaining:
                for tax in taxes:
                    if tax.amount:
                        tax.amount += remaining
                        break
            invoice.taxes = taxes
            invoice.save()
        return invoice

    @classmethod
    @ModelView.button
    def process(cls, sales):
        for sale in sales:
            for line in sale.lines:
                if line.shopify_identifier and line.quantity:
                    if not line.product:
                        raise SaleConfirmError(
                            gettext('web_shop_shopify'
                                '.msg_sale_line_without_product',
                                sale=sale.rec_name,
                                line=line.rec_name))
                    if not line.shopify_warehouse and line.movable:
                        raise SaleConfirmError(
                            gettext('web_shop_shopify'
                                '.msg_sale_line_without_warehouse',
                                sale=sale.rec_name,
                                line=line.rec_name))
        super().process(sales)
        for sale in sales:
            if not sale.web_shop or not sale.shopify_identifier:
                continue
            cls.__queue__._process_shopify(sale)

    def _process_shopify(self):
        """Sent updates to shopify

        The transaction is committed if fulfillment is created.
        """
        pool = Pool()
        Payment = pool.get('account.payment')
        with self.web_shop.shopify_session():
            for shipment in self.shipments:
                fulfillment = shipment.get_shopify(self)
                if fulfillment:
                    try:
                        result = shopify.GraphQL().execute(
                            MUTATION_FULFILLMENT_CREATE,
                            {'fulfillment': fulfillment}
                            )['data']['fulfillmentCreate']
                        if errors := result.get('userErrors'):
                            raise GraphQLException({'errors': errors})
                        fulfillment = result['fulfillment']
                    except GraphQLException as e:
                        raise ShopifyError(gettext(
                                'web_shop_shopify.msg_fulfillment_fail',
                                sale=self.rec_name,
                                error="\n".join(
                                    err['message'] for err in e.errors))
                            ) from e
                    shipment.set_shopify_identifier(
                        self, gid2id(fulfillment['id']))
                    Transaction().commit()
                elif shipment.state == 'cancelled':
                    fulfillment_id = shipment.get_shopify_identifier(self)
                    if fulfillment_id:
                        fulfillment_id = id2gid('Fulfillment', fulfillment_id)
                        result = shopify.GraphQL().execute(
                            MUTATION_FULFILLMENT_CANCEL,
                            {'id': fulfillment_id}
                            )['data']['fulfillmentCancel']
                        if errors := result.get('userErrors'):
                            raise GraphQLException({'errors': errors})

            # TODO: manage drop shipment

            shopify_id = id2gid('Order', self.shopify_identifier)
            if self.shipment_state == 'sent' or self.state == 'done':
                # TODO: manage shopping refund
                refund = self.get_shopify_refund(
                    shipping=self.shipment_state == 'none')
                if refund:
                    try:
                        result = shopify.GraphQL().execute(
                            MUTATION_REFUND_CREATE,
                            {'input': refund})['data']['refundCreate']
                        if errors := result.get('userErrors'):
                            raise GraphQLException({'errors': errors})
                    except GraphQLException as e:
                        raise ShopifyError(gettext(
                                'web_shop_shopify.msg_refund_fail',
                                sale=self.rec_name,
                                error="\n".join(
                                    err['message'] for err in e.errors))
                            ) from e
                    order = shopify.GraphQL().execute(
                        QUERY_ORDER % {
                            'fields': graphql.selection(self.shopify_fields()),
                            }, {'id': shopify_id})['data']['order']
                    Payment.get_from_shopify(self, order)

            shopify_id = id2gid('Order', self.shopify_identifier)
            order = shopify.GraphQL().execute(
                QUERY_ORDER_CLOSED, {'id': shopify_id})['data']['order']
            if self.state == 'done':
                if not order['closed']:
                    result = shopify.GraphQL().execute(
                        MUTATION_ORDER_CLOSE, {
                            'input': {
                                'id': shopify_id,
                                },
                            })['data']['orderClose']
                    if errors := result.get('userErrors'):
                        raise GraphQLException({'errors': errors})
            elif order['closed']:
                result = shopify.GraphQL().execute(
                    MUTATION_ORDER_OPEN, {
                        'input': {
                            'id': shopify_id,
                            },
                        })['data']['orderOpen']
                if errors := result.get('userErrors'):
                    raise GraphQLException({'errors': errors})

    def get_shopify_refund(self, shipping=False):
        order_id = id2gid('Order', self.shopify_identifier)
        shopify_line_items = graphql.iterate(
            QUERY_ORDER_FULFILLABLE_QUANTITIES,
            {'id': order_id}, 'order', 'lineItems')
        fulfillable_quantities = {
            gid2id(l['id']): l['fulfillableQuantity']
            for l in shopify_line_items}
        refund_line_items = list(
            self.get_shopify_refund_line_items(fulfillable_quantities))
        if not refund_line_items:
            return

        order = shopify.GraphQL().execute(
            QUERY_ORDER_SUGGESTED_REFUND, {
                'id': order_id,
                'refundShipping': shipping,
                'refundLineItems': refund_line_items})['data']['order']
        currencies = set()
        transactions = []
        for transaction in order['suggestedRefund']['suggestedTransactions']:
            amount = transaction['amountSet']['presentmentMoney']['amount']
            currencies.add(
                transaction['amountSet']['presentmentMoney']['currencyCode'])
            transactions.append({
                    'amount': amount,
                    'gateway': transaction['gateway'],
                    'kind': 'REFUND',
                    'orderId': order_id,
                    'parentId': transaction['parentTransaction']['id'],
                    })
        if not transactions:
            return
        currency, = currencies
        return {
            'orderId': order_id,
            'currency': currency,
            'refundLineItems': refund_line_items,
            'shipping': {
                'fullRefund': shipping,
                },
            'transactions': transactions,
            }

    def get_shopify_refund_line_items(self, fulfillable_quantities):
        pool = Pool()
        Uom = pool.get('product.uom')

        assert self.shipment_state == 'sent'
        location_id = None
        for shop_warehouse in self.web_shop.shopify_warehouses:
            if shop_warehouse.warehouse == self.warehouse:
                location_id = shop_warehouse.shopify_id
        for line in self.lines:
            if (line.type != 'line'
                    or not line.shopify_identifier
                    or not line.movable):
                continue
            fulfillable_quantity = fulfillable_quantities.get(
                line.shopify_identifier, 0)
            quantity = line.quantity
            for move in line.moves:
                if move.state == 'done':
                    quantity -= Uom.compute_qty(
                        move.unit, move.quantity, line.unit)
            quantity = min(fulfillable_quantity, quantity)
            if quantity > 0:
                yield {
                    'lineItemId': id2gid('LineItem', line.shopify_identifier),
                    'locationId': id2gid('Location', location_id),
                    'quantity': int(quantity),
                    'restockType': 'CANCEL',
                    }


class Sale_ShipmentCost(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def set_shipment_cost(self):
        if self.web_shop and self.web_shop.type == 'shopify':
            return []
        return super().set_shipment_cost()

    @classmethod
    def shopify_fields(cls):
        fields = super().shopify_fields()
        shipping_line = fields.setdefault('shippingLine', {})
        shipping_line.setdefault('code')
        shipping_line.setdefault('title')
        return fields

    @classmethod
    def get_from_shopify(cls, shop, order, sale=None):
        pool = Pool()
        Tax = pool.get('account.tax')

        sale = super().get_from_shopify(shop, order, sale=sale)

        shipment_cost_method = None
        if shipping_line := order['shippingLine']:
            available_carriers = sale.on_change_with_available_carriers()
            carrier = None
            for carrier in available_carriers:
                if carrier.shopify_match(shop, shipping_line):
                    carrier = carrier
                    break
            else:
                if available_carriers:
                    carrier = available_carriers[0]
            setattr_changed(sale, 'carrier', carrier)
            if sale.carrier:
                shipment_cost_method = 'order'
                for line in sale.lines:
                    if getattr(line, 'shipment_cost', None) is not None:
                        unit_price = line.unit_price
                        base_price = getattr(line, 'base_price', None)
                        if setattr_changed(
                                line, 'product', sale.carrier.carrier_product):
                            line.on_change_product()
                        unit_price = round_price(Tax.reverse_compute(
                                unit_price, line.taxes, sale.sale_date))
                        setattr_changed(line, 'unit_price', unit_price)
                        if base_price is not None:
                            base_price = round_price(Tax.reverse_compute(
                                    base_price, line.taxes, sale.sale_date))
                            setattr_changed(line, 'base_price', base_price)
        setattr_changed(sale, 'shipment_cost_method', shipment_cost_method)
        return sale


class Line(IdentifierMixin, metaclass=PoolMeta):
    __name__ = 'sale.line'

    shopify_warehouse = fields.Many2One(
        'stock.location', "Shopify Warehouse", readonly=True)

    @fields.depends('shopify_warehouse')
    def on_change_with_warehouse(self, name=None):
        warehouse = super().on_change_with_warehouse(name=name)
        if self.shopify_warehouse:
            warehouse = self.shopify_warehouse
        return warehouse

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.states['readonly'] = (
            cls.product.states['readonly']
            & ~((Eval('sale_state') == 'confirmed')
                & Eval('shopify_identifier')))

    @classmethod
    def shopify_fields(cls):
        return {
            'id': None,
            'quantity': None,
            'variant': {
                'id': None,
                },
            'variantTitle': None,
            'discountAllocations': {
                'allocatedAmountSet': {
                    'presentmentMoney': {
                        'amount': None,
                        },
                    },
                },
            'originalUnitPriceSet': {
                'presentmentMoney': {
                    'amount': None,
                    },
                },
            }

    @classmethod
    def get_from_shopify(
            cls, sale, line_item, quantity, warehouse=None, line=None):
        pool = Pool()
        Product = pool.get('product.product')
        Tax = pool.get('account.tax')

        if not line:
            line = cls(type='line')
            line.sale = sale
            line.shopify_identifier = gid2id(line_item['id'])
            line.product = None
        line.shopify_warehouse = warehouse
        assert line.shopify_identifier == gid2id(line_item['id'])
        if line_item['variant'] and line_item['variant']['id']:
            if product := Product.search_shopify_identifier(
                    sale.web_shop, gid2id(line_item['variant']['id'])):
                setattr_changed(line, 'product', product)
        if line.product:
            line._set_shopify_quantity(line.product, quantity)
            if line._changed_values():
                line.on_change_product()
        else:
            setattr_changed(line, 'quantity', quantity)
            setattr_changed(line, 'description', line_item['variantTitle'])
            setattr_changed(line, 'taxes', ())
        total_discount = sum(
            Decimal(d['allocatedAmountSet']['presentmentMoney']['amount'])
            for d in line_item['discountAllocations'])
        unit_price = Decimal(
            line_item['originalUnitPriceSet']['presentmentMoney']['amount'])
        if line_item['quantity']:
            unit_price *= line_item['quantity']
        unit_price -= total_discount
        if line_item['quantity']:
            unit_price /= line_item['quantity']
        unit_price = round_price(Tax.reverse_compute(
                unit_price, line.taxes, sale.sale_date))
        if line.product:
            line._set_shopify_unit_price(line.product, unit_price)
        else:
            setattr_changed(line, 'unit_price', unit_price)
        return line

    def _set_shopify_quantity(self, product, quantity):
        if product.shopify_uom.category == product.sale_uom.category:
            setattr_changed(self, 'unit', self.product.shopify_uom)
            setattr_changed(self, 'quantity', quantity)

    def _set_shopify_unit_price(self, product, unit_price):
        if product.shopify_uom.category == product.sale_uom.category:
            setattr_changed(self, 'unit_price', unit_price)

    @classmethod
    def get_from_shopify_shipping(cls, sale, shipping_line, line=None):
        pool = Pool()
        Tax = pool.get('account.tax')

        if not line:
            line = cls(type='line')
            line.sale = sale
            line.product = None
        line._set_shopify_shipping_product(sale, shipping_line)
        setattr_changed(line, 'quantity', 1)
        if line.product:
            if line._changed_values:
                line.on_change_product()
        else:
            setattr_changed(line, 'taxes', ())
        unit_price = Decimal(
            shipping_line['currentDiscountedPriceSet']
            ['presentmentMoney']['amount'])
        unit_price = round_price(Tax.reverse_compute(
                unit_price, line.taxes, sale.sale_date))
        setattr_changed(line, 'unit_price', unit_price)
        setattr_changed(line, 'description', shipping_line['title'])
        return line

    def _set_shopify_shipping_product(self, sale, shipping_line):
        pass

    def _get_invoice_line_quantity(self):
        quantity = super()._get_invoice_line_quantity()
        if self.sale.web_shop and self.sale.web_shop.type == 'shopify':
            if (self.sale.get_shipment_state() != 'sent'
                    and any(l.product.type != 'service'
                        for l in self.sale.lines if l.product)):
                quantity = 0
        return quantity


class Line_Discount(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @classmethod
    def get_from_shopify(
            cls, sale, line_item, quantity, warehouse=None, line=None):
        pool = Pool()
        Tax = pool.get('account.tax')
        line = super().get_from_shopify(
            sale, line_item, quantity, warehouse=warehouse, line=line)
        amount = Decimal(
            line_item['originalUnitPriceSet']['presentmentMoney']['amount'])
        setattr_changed(line, 'base_price', round_price(
                Tax.reverse_compute(amount, line.taxes, sale.sale_date)))
        return line

    @classmethod
    def get_from_shopify_shipping(cls, sale, shipping_line, line=None):
        line = super().get_from_shopify_shipping(
            sale, shipping_line, line=line)
        setattr_changed(line, 'base_price', Decimal(
                shipping_line['currentDiscountedPriceSet']['presentmentMoney']
                ['amount']))
        return line


class Line_SaleSecondaryUnit(metaclass=PoolMeta):
    __name__ = 'sale.line'

    def _set_shopify_quantity(self, product, quantity):
        super()._set_shopify_quantity(product, quantity)
        if (product.sale_secondary_uom
                and product.shopify_uom.category
                == product.sale_secondary_uom.category):
            changed = setattr_changed(self, 'unit', product.sale_uom)
            changed |= setattr_changed(
                self, 'secondary_unit', product.shopify_uom)
            if changed:
                self.on_change_product()
            if setattr_changed(self, 'secondary_quantity', quantity):
                self.on_change_secondary_quantity()

    def _set_shopify_unit_price(self, product, unit_price):
        super()._set_shopify_unit_price(product, unit_price)
        if (product.sale_secondary_uom
                and product.shopify_uom.category
                == product.sale_secondary_uom.category):
            if setattr_changed(self, 'secondary_unit_price', unit_price):
                self.on_change_secondary_unit_price()


class Line_ShipmentCost(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @classmethod
    def get_from_shopify_shipping(cls, sale, shipping_line, line=None):
        line = super().get_from_shopify_shipping(
            sale, shipping_line, line=line)
        setattr_changed(line, 'shipment_cost', Decimal(
                shipping_line['currentDiscountedPriceSet']['presentmentMoney']
                ['amount']))
        return line

    def _set_shopify_shipping_product(self, sale, shipping_line):
        super()._set_shopify_shipping_product(sale, shipping_line)
        if sale.carrier:
            setattr_changed(self, 'product', sale.carrier.carrier_product)


class Line_Kit(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @classmethod
    def get_from_shopify(
            cls, sale, line_item, quantity, warehouse=None, line=None):
        pool = Pool()
        UoM = pool.get('product.uom')
        Component = pool.get('sale.line.component')
        line = super().get_from_shopify(
            sale, line_item, quantity, warehouse=warehouse, line=line)
        if getattr(line, 'components', None):
            quantity = UoM.compute_qty(
                line.unit, line.quantity,
                line.product.default_uom, round=False)
            for component in line.components:
                if not component.fixed:
                    quantity = component.unit.round(
                        quantity * component.quantity_ratio)
                    setattr_changed(component, 'quantity', quantity)
            line.components = line.components
        elif (getattr(sale, 'state', 'draft') != 'draft'
                and line.product
                and line.product.type == 'kit'):
            components = []
            for component in line.product.components_used:
                components.append(line.get_component(component))
            Component.set_price_ratio(components, line.quantity)
            line.components = components
        return line

# TODO: refund as return sale
