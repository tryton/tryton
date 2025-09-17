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

from .common import IdentifierMixin, setattr_changed
from .exceptions import ShopifyError


class Sale(IdentifierMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'

    shopify_tax_adjustment = Monetary(
        "Shopify Tax Adjustment",
        currency='currency', digits='currency', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('web_shop_shopify_identifier_unique',
                Unique(t, t.web_shop, t.shopify_identifier_signed),
                'web_shop_shopify.msg_identifier_sale_web_shop_unique'),
            ]

    @fields.depends('shopify_tax_adjustment')
    def get_tax_amount(self):
        amount = super().get_tax_amount()
        if self.shopify_tax_adjustment:
            amount += self.shopify_tax_adjustment
        return amount

    @classmethod
    def get_from_shopify(cls, shop, order, sale=None):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        Currency = pool.get('currency.currency')
        Line = pool.get('sale.line')

        if getattr(order, 'customer', None):
            party = Party.get_from_shopify(shop, order.customer)
            party.save()
            party.set_shopify_identifier(shop, order.customer.id)
        else:
            party = shop.guest_party

        if not sale:
            sale = shop.get_sale(party=party)
            sale.shopify_identifier = order.id
        setattr_changed(sale, 'party', party)

        assert sale.shopify_identifier == order.id
        if order.location_id:
            for shop_warehouse in shop.shopify_warehouses:
                if shop_warehouse.shopify_id == str(order.location_id):
                    sale.warehouse = shop_warehouse.warehouse
                    break
        if sale.currency.code != order.presentment_currency:
            sale.currency, = Currency.search([
                    ('code', '=', order.presentment_currency),
                    ], limit=1)

        if sale.party != shop.guest_party:
            if getattr(order, 'shipping_address', None):
                shipment_address = party.get_address_from_shopify(
                    order.shipping_address)
            else:
                shipment_address = None
            if getattr(order, 'billing_address', None):
                invoice_address = party.get_address_from_shopify(
                    order.billing_address)
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

        setattr_changed(sale, 'reference', order.name)
        setattr_changed(sale, 'comment', order.note)
        setattr_changed(sale, 'sale_date', dateutil.parser.isoparse(
                order.processed_at or order.created_at).date())

        if order.phone:
            for contact_mechanism in party.contact_mechanisms:
                if (contact_mechanism.type in {'phone', 'mobile'}
                        and (contact_mechanism.value_compact
                            == contact_mechanism.format_value_compact(
                                order.phone, contact_mechanism.type))):
                    break
            else:
                contact_mechanism = ContactMechanism(
                    party=party, type='phone', value=order.phone)
            setattr_changed(sale, 'contact', contact_mechanism)

        refund_line_items = defaultdict(list)
        for refund in order.refunds:
            for refund_line_item in refund.refund_line_items:
                refund_line_items[refund_line_item.line_item_id].append(
                    refund_line_item)

        id2line = {
            l.shopify_identifier: l for l in getattr(sale, 'lines', [])
            if l.shopify_identifier}
        shipping_lines = [
            l for l in getattr(sale, 'lines', []) if not
            l.shopify_identifier]
        lines = []
        for line_item in order.line_items:
            line = id2line.pop(line_item.id, None)
            quantity = line_item.quantity
            for refund_line_item in refund_line_items[line_item.id]:
                quantity -= refund_line_item.quantity
            lines.append(Line.get_from_shopify(
                    sale, line_item, quantity, line=line))
        for shipping_line, line in zip_longest(
                order.shipping_lines, shipping_lines):
            if shipping_line:
                line = Line.get_from_shopify_shipping(
                    sale, shipping_line, line=line)
            else:
                line.quantity = 0
            lines.append(line)
        for line in id2line.values():
            line.quantity = 0
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
                if not line.product and line.shopify_identifier:
                    raise SaleConfirmError(
                        gettext('web_shop_shopify'
                            '.msg_sale_line_without_product',
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
                    if not fulfillment.save():
                        raise ShopifyError(gettext(
                                'web_shop_shopify.msg_fulfillment_fail',
                                sale=self.rec_name,
                                error="\n".join(
                                    fulfillment.errors.full_messages())))
                    shipment.set_shopify_identifier(self, fulfillment.id)
                    Transaction().commit()

            # TODO: manage drop shipment

            if self.shipment_state == 'sent' or self.state == 'done':
                # TODO: manage shopping refund
                refund = self.get_shopify_refund(shipping={
                        'full_refund': self.shipment_state == 'none',
                        })
                if refund:
                    if not refund.save():
                        raise ShopifyError(gettext(
                                'web_shop_shopify.msg_refund_fail',
                                sale=self.rec_name,
                                error="\n".join(
                                    refund.errors.full_messages())))
                    order = shopify.Order.find(self.shopify_identifier)
                    Payment.get_from_shopify(self, order)

            if self.state == 'done':
                order = shopify.Order.find(self.shopify_identifier)
                order.close()

    def get_shopify_refund(self, shipping):
        order = shopify.Order.find(self.shopify_identifier)
        fulfillable_quantities = {
            l.id: l.fulfillable_quantity for l in order.line_items}
        refund_line_items = list(
            self.get_shopify_refund_line_items(fulfillable_quantities))
        if not refund_line_items:
            return

        refund = shopify.Refund.calculate(
            self.shopify_identifier, shipping={
                'full_refund': False,
                },
            refund_line_items=refund_line_items)
        refund.refund_line_items = refund_line_items
        for transaction in refund.transactions:
            transaction.kind = 'refund'
        return refund

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
                    or not (line.product
                        and line.product.type in
                        line.get_move_product_types())):
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
                    'line_item_id': line.shopify_identifier,
                    'quantity': int(quantity),
                    'restock_type': 'cancel',
                    'location_id': location_id,
                    }


class Sale_ShipmentCost(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def set_shipment_cost(self):
        if self.web_shop and self.web_shop.type == 'shopify':
            return []
        return super().set_shipment_cost()

    @classmethod
    def get_from_shopify(cls, shop, order, sale=None):
        pool = Pool()
        Tax = pool.get('account.tax')

        sale = super().get_from_shopify(shop, order, sale=sale)

        shipment_cost_method = None
        if order.shipping_lines:
            available_carriers = sale.on_change_with_available_carriers()
            carrier = None
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

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.states['readonly'] = (
            cls.product.states['readonly']
            & ~((Eval('sale_state') == 'confirmed')
                & Eval('shopify_identifier')))

    @classmethod
    def get_from_shopify(cls, sale, line_item, quantity, line=None):
        pool = Pool()
        Product = pool.get('product.product')
        Tax = pool.get('account.tax')

        if not line:
            line = cls(type='line')
            line.sale = sale
            line.shopify_identifier = line_item.id
            line.product = None
        assert line.shopify_identifier == line_item.id
        if getattr(line_item, 'variant_id', None):
            if product := Product.search_shopify_identifier(
                    sale.web_shop, line_item.variant_id):
                setattr_changed(line, 'product', product)
        if line.product:
            line._set_shopify_quantity(line.product, quantity)
            if line._changed_values:
                line.on_change_product()
        else:
            setattr_changed(line, 'quantity', quantity)
            setattr_changed(line, 'description', line_item.title)
            setattr_changed(line, 'taxes', ())
        total_discount = sum(
            Decimal(d.amount) for d in line_item.discount_allocations)
        unit_price = ((
                (Decimal(line_item.price) * (line_item.quantity or 1))
                - Decimal(total_discount))
            / (line_item.quantity or 1))
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
        if not line:
            line = cls(type='line')
            line.sale = sale
        setattr_changed(line, 'quantity', 1)
        setattr_changed(
            line, 'unit_price',
            round_price(Decimal(shipping_line.discounted_price)))
        setattr_changed(line, 'description', shipping_line.title)
        return line

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
    def get_from_shopify(cls, sale, line_item, quantity, line=None):
        pool = Pool()
        Tax = pool.get('account.tax')
        line = super().get_from_shopify(sale, line_item, quantity, line=line)
        setattr_changed(line, 'base_price', round_price(
                Tax.reverse_compute(
                    Decimal(line_item.price), line.taxes, sale.sale_date)))
        return line

    @classmethod
    def get_from_shopify_shipping(cls, sale, shipping_line, line=None):
        line = super().get_from_shopify_shipping(
            sale, shipping_line, line=line)
        setattr_changed(line, 'base_price', Decimal(shipping_line.price))
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
        setattr_changed(line, 'shipment_cost', Decimal(shipping_line.price))
        return line

# TODO: refund as return sale
