# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool

from trytond.modules.account.tax import TaxableMixin

from .exceptions import BadRequest
from .web import split_name


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @property
    def vsf_id(self):
        if self.web_shop:
            if self.web_shop.guest_party == self.party:
                return self.web_id
            else:
                return self.id

    def get_vsf_user_order_history(self):
        firstname, lastname = split_name(self.party.name)
        return {
            'entity_id': self.id,
            'increment_id': self.number,
            'created_at': self.create_date.isoformat(),
            'customer_firstname': firstname,
            'customer_lastname': lastname,
            'grand_total': float(self.total_amount),
            'status': self.state_string,
            'items': [
                line.get_vsf_user_order_history() for line in self.lines],
            }

    @classmethod
    def search_vsf(cls, cart_id, shop, user=None):
        domain = [
            ('web_shop', '=', shop.id),
            ('state', '=', 'draft'),
            ]
        # cart_id may be either id and web_id
        cart_id_domain = ['OR']
        domain.append(cart_id_domain)
        try:
            sale_id = int(cart_id)
        except ValueError:
            pass
        else:
            if user:
                party = user.party
                cart_id_domain.append([
                        ('id', '=', sale_id),
                        ('party', '=', party.id),
                        ])
        cart_id_domain.append(('web_id', '=', cart_id))
        try:
            sale, = cls.search(domain, limit=1)
        except ValueError:
            raise BadRequest()
        return sale

    @property
    def vsf_subtotal(self):
        return self.untaxed_amount

    def set_vsf(self, data, user=None):
        if user and self.web_shop and self.party == self.web_shop.guest_party:
            self.party = user.party
            self.on_change_party()
        if user and 'addressInformation' in data:
            addresses = data['addressInformation']
            address_data = addresses.get('shippingAddress')
            if address_data:
                address = user.set_vsf_address(address_data, self.party)
                if address.party != self.party:
                    self.shipment_party = address.party
                self.shipment_address = address
            address_data = addresses.get('billingAddress')
            if address_data:
                if address_data != addresses.get('shippingAddress'):
                    address = user.set_vsf_address(address_data, self.party)
                if address.party != self.party:
                    self.invoice_party = address.party
                self.invoice_address = address

    def get_vsf(self):
        return {
            'grand_total': float(self.total_amount),
            'items': [line.get_vsf() for line in self.lines if line.product],
            'total_segments': [{
                    'code': 'subtotal',
                    'title': gettext('web_shop_vue_storefront.msg_subtotal'),
                    'value': float(self.vsf_subtotal),
                    }, {
                    'code': 'tax',
                    'title': gettext('web_shop_vue_storefront.msg_tax'),
                    'value': float(self.tax_amount),
                    }, {
                    'code': 'grand_total',
                    'title': gettext(
                        'web_shop_vue_storefront.msg_grand_total'),
                    'value': float(self.total_amount),
                    }],
            }


class SaleShipmentCost(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def get_vsf(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        item = super().get_vsf()
        if self.carrier:
            cost = self.compute_shipment_cost()
            cost_line = self.get_shipment_cost_line(cost)
            taxes = Tax.compute(cost_line.taxes, cost, 1)
            cost += sum(t['amount'] for t in taxes)
            cost = float(self.currency.round(cost))
            item['grand_total'] += cost
            item['total_segments'].insert(1, {
                    'code': 'shipping',
                    'title': gettext('web_shop_vue_storefront.msg_shipping'),
                    'value': cost,
                    })
            for segment in item['total_segments']:
                if segment['code'] == 'grand_total':
                    segment['value'] += cost
        return item

    def set_vsf_shipping_methods(self, data):
        pool = Pool()
        Country = pool.get('country.country')
        Address = pool.get('party.address')
        try:
            country, = Country.search([
                    ('code', '=', data['address']['country_id']),
                    ])
        except ValueError:
            raise BadRequest()
        if not self.shipment_address:
            self.shipment_address = Address()
        self.shipment_address.country = country

    def set_vsf(self, data, user):
        pool = Pool()
        Carrier = pool.get('carrier')
        super().set_vsf(data, user)
        if 'addressInformation' in data:
            if data['addressInformation']['shipping_carrier_code']:
                try:
                    carrier_id = int(
                        data['addressInformation']['shipping_carrier_code'])
                except ValueError:
                    raise BadRequest()
                try:
                    carrier, = Carrier.search([
                            ('id', '=', carrier_id),
                            ], limit=1)
                except ValueError:
                    raise BadRequest()
            else:
                carrier = None
            self.carrier = carrier


class Line(TaxableMixin, metaclass=PoolMeta):
    __name__ = 'sale.line'

    @property
    def taxable_lines(self):
        return [(
                getattr(self, 'taxes', None) or [],
                getattr(self, 'unit_price', None) or Decimal(0),
                getattr(self, 'quantity', None) or 0,
                None,
                )]

    @property
    def vsf_tax_amount(self):
        return sum(
            (v['amount'] for v in self._get_taxes().values()), Decimal(0))

    def get_vsf_user_order_history(self):
        amount_incl_tax = self.amount + self.vsf_tax_amount
        digits = self.__class__.unit_price.digits
        price_incl_tax = (
            amount_incl_tax / Decimal(str(self.quantity))
            ).quantize(Decimal(1) / 10 ** digits[1])
        return {
            'name': self.product.name if self.product else '',
            'sku': self.product.vsf_sku if self.product else '',
            'price_incl_tax': float(price_incl_tax),
            'qty_ordered': self.quantity,
            'row_total_incl_tax': float(amount_incl_tax),
            }

    def get_vsf(self):
        assert self.product
        amount_incl_tax = self.amount + self.vsf_tax_amount
        digits = self.__class__.unit_price.digits
        price_incl_tax = (
            amount_incl_tax / Decimal(str(self.quantity))
            ).quantize(Decimal(1) / 10 ** digits[1])
        return {
            'item_id': self.id,
            'sku': self.product.vsf_sku,
            'qty': self.quantity,
            'name': self.product.name,
            'price': float(price_incl_tax),
            'product_type': self.product.vsf_type_id,
            'quote_id': self.sale.id,
            'product_option': {
                'extension_attributes': {
                    },
                },
            }

    def set_vsf(self, data):
        pool = Pool()
        Product = pool.get('product.product')
        try:
            self.product, = Product.search([
                    ('vsf_sku', '=', data['sku']),
                    ], limit=1)
        except ValueError:
            raise BadRequest()
        self.quantity = data['qty']
        self.on_change_product()


class LineAttribute(metaclass=PoolMeta):
    __name__ = 'sale.line'

    def get_vsf_cart(self):
        assert self.sale.web_shop
        item = super().get_vsf_cart()
        if self.product.attributes_set:
            product_option = item['product_option']
            extension_attributes = product_option['extension_attributes']
            extension_attributes['configurable_item_options'] = options = []
            for attribute in self.product.attributes_set.attributes:
                if attribute not in self.sale.web_shop.attributes:
                    continue
                options.append({
                        'option_id': attribute.vsf_identifier.id,
                        'option_value': self.attributes.get(attribute.name),
                        })
        return item
