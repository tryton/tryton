=========================
Web Shop Shopify Scenario
=========================

Imports::

    >>> import os
    >>> import random
    >>> import string
    >>> import time
    >>> import urllib.request
    >>> from decimal import Decimal
    >>> from itertools import cycle
    >>> from unittest.mock import patch

    >>> import shopify
    >>> from shopify.api_version import ApiVersion

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, create_tax, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.product_image.product import ImageURLMixin
    >>> from trytond.modules.web_shop_shopify.common import gid2id, id2gid
    >>> from trytond.modules.web_shop_shopify.product import Template
    >>> from trytond.modules.web_shop_shopify.tests import tools
    >>> from trytond.modules.web_shop_shopify.web import Shop
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertTrue

    >>> FETCH_SLEEP, MAX_SLEEP = 1, 10

Patch image URL::

    >>> get_image_url = patch.object(
    ...     ImageURLMixin, 'get_image_url').start()
    >>> get_image_url.side_effect = cycle([
    ...         'https://downloads.tryton.org/tests/shopify/chair.jpg',
    ...         'https://downloads.tryton.org/tests/shopify/chair-black.jpg',
    ...         'https://downloads.tryton.org/tests/shopify/chair-white.jpg',
    ...         ])

Activate modules::

    >>> config = activate_modules([
    ...         'web_shop_shopify',
    ...         'account_payment_clearing',
    ...         'carrier',
    ...         'customs',
    ...         'product_measurements',
    ...         'product_image',
    ...         'sale_discount',
    ...         'sale_shipment_cost',
    ...         ],
    ...     create_company, create_chart)

    >>> Account = Model.get('account.account')
    >>> Carrier = Model.get('carrier')
    >>> CarrierSelection = Model.get('carrier.selection')
    >>> Category = Model.get('product.category')
    >>> Country = Model.get('country.country')
    >>> Cron = Model.get('ir.cron')
    >>> Inventory = Model.get('stock.inventory')
    >>> Journal = Model.get('account.journal')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> Product = Model.get('product.product')
    >>> ProductAttribute = Model.get('product.attribute')
    >>> ProductAttributeSet = Model.get('product.attribute.set')
    >>> ProductInventoryItem = Model.get('product.shopify_inventory_item')
    >>> ProductTemplate = Model.get('product.template')
    >>> Sale = Model.get('sale.sale')
    >>> ShopifyIdentifier = Model.get('web.shop.shopify_identifier')
    >>> Tariff = Model.get('customs.tariff.code')
    >>> Uom = Model.get('product.uom')
    >>> WebShop = Model.get('web.shop')

Set metafields to product::

    >>> def get_shopify_metafields(self, shop):
    ...     return {
    ...         'global.test': {
    ...             'type': 'single_line_text_field',
    ...             'value': self.name,
    ...             },
    ...         }

    >>> Template.get_shopify_metafields = get_shopify_metafields

    >>> def managed_metafields(self):
    ...     return {'global.test'}

    >>> Shop.managed_metafields = managed_metafields

Create country::

    >>> belgium = Country(name="Belgium", code='BE')
    >>> belgium.save()
    >>> china = Country(name="China", code='CN')
    >>> china.save()

Get company::

    >>> company = get_company()

Get accounts::

    >>> accounts = get_accounts()

Create tax::

    >>> tax = create_tax(Decimal('.10'))

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Create payment journal::

    >>> shopify_account = Account(parent=accounts['receivable'].parent)
    >>> shopify_account.name = "Shopify"
    >>> shopify_account.type = accounts['receivable'].type
    >>> shopify_account.reconcile = True
    >>> shopify_account.save()

    >>> payment_journal = PaymentJournal()
    >>> payment_journal.name = "Shopify"
    >>> payment_journal.process_method = 'shopify'
    >>> payment_journal.clearing_journal, = Journal.find([('code', '=', 'REV')])
    >>> payment_journal.clearing_account = shopify_account
    >>> payment_journal.save()

Define a web shop::

    >>> web_shop = WebShop(name="Web Shop")
    >>> web_shop.type = 'shopify'
    >>> web_shop.shopify_url = os.getenv('SHOPIFY_URL')
    >>> web_shop.shopify_password = os.getenv('SHOPIFY_PASSWORD')
    >>> web_shop.shopify_version = sorted(ApiVersion.versions, reverse=True)[1]
    >>> shop_warehouse = web_shop.shopify_warehouses.new()
    >>> shop_warehouse.warehouse, = Location.find([('type', '=', 'warehouse')])
    >>> shopify_payment_journal = web_shop.shopify_payment_journals.new()
    >>> shopify_payment_journal.journal = payment_journal
    >>> web_shop.save()

    >>> shopify.ShopifyResource.activate_session(shopify.Session(
    ...         web_shop.shopify_url,
    ...         web_shop.shopify_version,
    ...         web_shop.shopify_password))

    >>> location = tools.get_location()

    >>> shop_warehouse, = web_shop.shopify_warehouses
    >>> shop_warehouse.shopify_id = str(gid2id(location['id']))
    >>> web_shop.save()

Create categories::

    >>> category1 = Category(name="Category 1")
    >>> category1.save()
    >>> sub_category = Category(name="Sub Category", parent=category1)
    >>> sub_category.save()
    >>> category2 = Category(name="Category 2")
    >>> category2.save()

    >>> account_category = Category(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.customer_taxes.append(tax)
    >>> account_category.save()

    >>> account_category_shipping = Category(name="Account Category Shipping")
    >>> account_category_shipping.accounting = True
    >>> account_category_shipping.account_expense = accounts['expense']
    >>> account_category_shipping.account_revenue = accounts['revenue']
    >>> account_category_shipping.save()

Create attribute set::

    >>> attribute_set = ProductAttributeSet(name="Attributes")
    >>> attribute = attribute_set.attributes.new()
    >>> attribute.name = 'color'
    >>> attribute.string = "Color"
    >>> attribute.type_ = 'selection'
    >>> attribute.selection = "blue:Blue\nred:Red"
    >>> attribute_set.save()
    >>> attribute = attribute_set.attributes.new()
    >>> attribute.name = 'check'
    >>> attribute.string = "Check"
    >>> attribute.type_ = 'boolean'
    >>> attribute_set.save()
    >>> attribute1, attribute2 = attribute_set.attributes
    >>> attribute_set.shopify_option1 = attribute1
    >>> attribute_set.shopify_option2 = attribute2
    >>> attribute_set.save()

Create tariff codes::

    >>> tariff1 = Tariff(code='170390')
    >>> tariff1.save()
    >>> tariff2 = Tariff(code='17039099', country=belgium)
    >>> tariff2.save()

Create products::

    >>> unit, = Uom.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Product 1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.web_shop_description = "<p>Product description</p>"
    >>> template.shopify_handle = 'product-%s' % random.randint(0, 1000)
    >>> template.list_price = round(Decimal('9.99') / (1 + tax.rate), 4)
    >>> template.account_category = account_category
    >>> template.categories.append(Category(sub_category.id))
    >>> template.country_of_origin = china
    >>> _ = template.tariff_codes.new(tariff_code=tariff1)
    >>> _ = template.tariff_codes.new(tariff_code=tariff2)
    >>> template.weight = 10
    >>> template.weight_uom, = Uom.find([('name', '=', "Carat")])
    >>> template.save()
    >>> product1, = template.products
    >>> product1.suffix_code = 'PROD1'
    >>> product1.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product 2"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.salable = True
    >>> template.list_price = round(Decimal('20') / (1 + tax.rate), 4)
    >>> template.account_category = account_category
    >>> template.categories.append(Category(category2.id))
    >>> template.save()
    >>> product2, = template.products
    >>> product2.suffix_code = 'PROD2'
    >>> product2.save()

    >>> variant = ProductTemplate()
    >>> variant.name = "Variant"
    >>> variant.code = "VAR"
    >>> variant.default_uom = unit
    >>> variant.type = 'goods'
    >>> variant.salable = True
    >>> variant.list_price = round(Decimal('50') / (1 + tax.rate), 4)
    >>> variant.attribute_set = attribute_set
    >>> variant.account_category = account_category
    >>> variant.categories.append(Category(category1.id))
    >>> variant.categories.append(Category(category2.id))
    >>> image = variant.images.new(web_shop=True)
    >>> image.image = urllib.request.urlopen(
    ...     'https://downloads.tryton.org/tests/shopify/chair.jpg').read()
    >>> variant1, = variant.products
    >>> variant1.suffix_code = "1"
    >>> variant1.attributes = {
    ...     'color': 'blue',
    ...     'check': True,
    ...     }
    >>> variant2 = variant.products.new()
    >>> variant2.suffix_code = "2"
    >>> variant2.attributes = {
    ...     'color': 'red',
    ...     'check': False,
    ...     }
    >>> variant.save()
    >>> variant1, variant2 = variant.products

    >>> image = variant1.images.new(web_shop=True, template=variant)
    >>> image.image = urllib.request.urlopen(
    ...     'https://downloads.tryton.org/tests/shopify/chair-black.jpg').read()
    >>> variant1.save()

    >>> image = variant2.images.new(web_shop=True, template=variant)
    >>> image.image = urllib.request.urlopen(
    ...     'https://downloads.tryton.org/tests/shopify/chair-white.jpg').read()
    >>> variant2.save()

Create carriers::

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.list_price = Decimal('3')
    >>> carrier_template.account_category = account_category_shipping
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products
    >>> carrier_product.cost_price = Decimal('2')
    >>> carrier_product.save()

    >>> carrier1 = Carrier()
    >>> party = Party(name="Carrier 1")
    >>> party.save()
    >>> carrier1.party = party
    >>> carrier1.carrier_product = carrier_product
    >>> carrier1.save()

    >>> carrier2 = Carrier()
    >>> party = Party(name="Carrier 2")
    >>> party.save()
    >>> carrier2.party = party
    >>> carrier2.carrier_product = carrier_product
    >>> _ = carrier2.shopify_selections.new(code='SHIP')
    >>> carrier2.save()

    >>> CarrierSelection(carrier=carrier1).save()
    >>> CarrierSelection(carrier=carrier2).save()

Fill warehouse::

    >>> inventory = Inventory()
    >>> inventory.location, = Location.find([('code', '=', 'STO')])
    >>> line = inventory.lines.new()
    >>> line.product = product1
    >>> line.quantity = 10
    >>> line = inventory.lines.new()
    >>> line.product = variant1
    >>> line.quantity = 5
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Set categories, products and attributes to web shop::

    >>> web_shop.categories.extend([
    ...         Category(category1.id),
    ...         Category(sub_category.id),
    ...         Category(category2.id)])
    >>> web_shop.products.extend([
    ...         Product(product1.id),
    ...         Product(product2.id),
    ...         Product(variant1.id),
    ...         Product(variant2.id)])
    >>> web_shop.save()

Run update product::

    >>> cron_update_product, = Cron.find([
    ...     ('method', '=', 'web.shop|shopify_update_product'),
    ...     ])
    >>> cron_update_product.click('run_once')

    >>> category1.reload()
    >>> len(category1.shopify_identifiers)
    1
    >>> category2.reload()
    >>> len(category2.shopify_identifiers)
    1

    >>> product1.reload()
    >>> len(product1.shopify_identifiers)
    1
    >>> len(product1.template.shopify_identifiers)
    1
    >>> product2.reload()
    >>> len(product2.shopify_identifiers)
    1
    >>> len(product2.template.shopify_identifiers)
    1
    >>> variant1.reload()
    >>> len(variant1.shopify_identifiers)
    1
    >>> variant2.reload()
    >>> len(variant2.shopify_identifiers)
    1
    >>> variant.reload()
    >>> len(variant.shopify_identifiers)
    1
    >>> all(i.shopify_identifiers for i in variant.images)
    True

Run update inventory::

    >>> cron_update_inventory, = Cron.find([
    ...     ('method', '=', 'web.shop|shopify_update_inventory'),
    ...     ])
    >>> cron_update_inventory.click('run_once')

Check inventory item::

    >>> inventory_items = ProductInventoryItem.find([])
    >>> inventory_item_ids = [i.shopify_identifier
    ...     for inv in inventory_items for i in inv.shopify_identifiers]
    >>> for _ in range(MAX_SLEEP):
    ...     inventory_levels = tools.get_inventory_levels(location)
    ...     if inventory_levels and len(inventory_levels) == 2:
    ...         break
    ...     time.sleep(FETCH_SLEEP)
    >>> sorted(l['quantities'][0]['quantity'] for l in inventory_levels
    ...     if l['quantities'][0]['quantity']
    ...     and gid2id(l['item']['id']) in inventory_item_ids)
    [5, 10]

Remove a category, a product and an image::

    >>> _ = web_shop.categories.pop(web_shop.categories.index(category2))
    >>> _ = web_shop.products.pop(web_shop.products.index(product2))
    >>> web_shop.save()
    >>> variant2.images.remove(variant2.images[0])
    >>> variant2.save()

Rename a category::

    >>> sub_category.name = "Sub-category"
    >>> sub_category.save()
    >>> identifier, = sub_category.shopify_identifiers
    >>> bool(identifier.to_update)
    True

Update attribute::

    >>> attribute, = [a for a in attribute_set.attributes if a.name == 'color']
    >>> attribute.selection += "\ngreen:Green"
    >>> attribute.save()

Run update product::

    >>> cron_update_product, = Cron.find([
    ...     ('method', '=', 'web.shop|shopify_update_product'),
    ...     ])
    >>> cron_update_product.click('run_once')

    >>> category1.reload()
    >>> len(category1.shopify_identifiers)
    1
    >>> category2.reload()
    >>> len(category2.shopify_identifiers)
    0

    >>> sub_category.reload()
    >>> identifier, = sub_category.shopify_identifiers
    >>> bool(identifier.to_update)
    False

    >>> product1.reload()
    >>> len(product1.shopify_identifiers)
    1
    >>> len(product1.template.shopify_identifiers)
    1
    >>> product2.reload()
    >>> len(product2.shopify_identifiers)
    0
    >>> identifier, = product2.template.shopify_identifiers
    >>> tools.get_product(identifier.shopify_identifier)['status']
    'ARCHIVED'
    >>> variant1.reload()
    >>> len(variant1.shopify_identifiers)
    1
    >>> variant2.reload()
    >>> len(variant2.shopify_identifiers)
    1
    >>> variant.reload()
    >>> len(variant.shopify_identifiers)
    1
    >>> all(i.shopify_identifiers for i in variant1.images)
    True
    >>> any(i.shopify_identifiers for i in variant2.images)
    False

Create an order on Shopify::

    >>> customer_phone = '+32-495-555-' + (
    ...     ''.join(random.choice(string.digits) for _ in range(3)))
    >>> customer_address_phone = '+32-495-555-' + (
    ...     ''.join(random.choice(string.digits) for _ in range(3)))
    >>> customer = tools.create_customer({
    ...         'lastName': "Customer",
    ...         'email': (''.join(
    ...                 random.choice(string.ascii_letters) for _ in range(10))
    ...             + '@example.com'),
    ...         'phone': customer_phone,
    ...         'locale': 'en-CA',
    ...         })

    >>> order = tools.create_order({
    ...         'customer': {
    ...             'toAssociate': {
    ...                 'id': customer['id'],
    ...                 },
    ...             },
    ...         'shippingAddress': {
    ...                 'lastName': "Customer",
    ...                 'address1': "Street",
    ...                 'city': "City",
    ...                 'countryCode': 'BE',
    ...                 'phone': customer_address_phone,
    ...                 },
    ...         'lineItems': [{
    ...             'variantId': id2gid(
    ...                 'ProductVariant',
    ...                 product1.shopify_identifiers[0].shopify_identifier),
    ...             'quantity': 1,
    ...             }, {
    ...             'variantId': id2gid(
    ...                 'ProductVariant',
    ...                 product1.shopify_identifiers[0].shopify_identifier),
    ...             'quantity': 1,
    ...             }, {
    ...             'variantId': id2gid(
    ...                 'ProductVariant',
    ...                 variant1.shopify_identifiers[0].shopify_identifier),
    ...             'quantity': 5,
    ...             }],
    ...         'shippingLines': [{
    ...             'code': 'SHIP',
    ...             'title': "Shipping",
    ...             'priceSet': {
    ...                 'shopMoney': {
    ...                     'amount': 4,
    ...                     'currencyCode': company.currency.code,
    ...                     },
    ...                 },
    ...             }],
    ...         'discountCode': {
    ...             'itemFixedDiscountCode': {
    ...                 'amountSet': {
    ...                     'shopMoney': {
    ...                         'amount': 15,
    ...                         'currencyCode': company.currency.code,
    ...                         },
    ...                     },
    ...                 'code': "CODE",
    ...                 },
    ...             },
    ...         'financialStatus': 'AUTHORIZED',
    ...         'transactions': [{
    ...             'kind': 'AUTHORIZATION',
    ...             'status': 'SUCCESS',
    ...             'amountSet': {
    ...                 'shopMoney': {
    ...                     'amount': 258.98,
    ...                     'currencyCode': company.currency.code,
    ...                     },
    ...                 },
    ...             'test': True,
    ...             }],
    ...         })
    >>> order['totalPriceSet']['presentmentMoney']['amount']
    '258.98'
    >>> order['displayFinancialStatus']
    'AUTHORIZED'
    >>> order['displayFulfillmentStatus']
    'UNFULFILLED'

Run fetch order::

    >>> with config.set_context(shopify_orders=[gid2id(order['id'])]):
    ...     cron_fetch_order, = Cron.find([
    ...         ('method', '=', 'web.shop|shopify_fetch_order'),
    ...         ])
    ...     cron_fetch_order.click('run_once')

    >>> sale, = Sale.find([])
    >>> sale.shopify_tax_adjustment
    Decimal('0.01')
    >>> len(sale.lines)
    4
    >>> sorted([l.unit_price for l in sale.lines])
    [Decimal('4.0000'), Decimal('8.5727'), Decimal('8.5727'), Decimal('42.9309')]
    >>> any(l.product == carrier_product for l in sale.lines)
    True
    >>> sale.total_amount
    Decimal('258.98')
    >>> len(sale.payments)
    1
    >>> payment, = sale.payments
    >>> payment.state
    'processing'
    >>> payment.amount
    Decimal('0')
    >>> assertEqual(sale.carrier, carrier2)
    >>> sale.state
    'quotation'
    >>> sale.party.name
    'Customer'
    >>> sale.party.lang.code
    'en'
    >>> assertTrue(sale.party.email)
    >>> assertEqual(sale.party.phone.replace(' ', ''), customer_phone.replace('-', ''))
    >>> address, = sale.party.addresses
    >>> address_contact_mechanism, = address.contact_mechanisms
    >>> assertEqual(
    ...     address_contact_mechanism.value.replace(' ', ''),
    ...     customer_address_phone.replace('-', ''))
    >>> len(sale.party.contact_mechanisms)
    3
    >>> assertTrue(sale.web_status_url)

Capture full amount::

    >>> transaction = tools.capture_order(
    ...     order['id'], 258.98, order['transactions'][0]['id'])

    >>> with config.set_context(shopify_orders=[gid2id(order['id'])]):
    ...     cron_update_order, = Cron.find([
    ...         ('method', '=', 'web.shop|shopify_update_order'),
    ...         ])
    ...     cron_update_order.click('run_once')

    >>> sale.reload()
    >>> len(sale.payments)
    1
    >>> payment, = sale.payments
    >>> payment.state
    'succeeded'
    >>> sale.state
    'processing'
    >>> len(sale.invoices)
    0
    >>> len(sale.party.contact_mechanisms)
    3

Make a partial shipment::

    >>> shipment, = sale.shipments
    >>> move, = [m for m in shipment.inventory_moves if m.product == variant1]
    >>> move.quantity = 3
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> sale.reload()
    >>> len(sale.invoices)
    0

    >>> order = tools.get_order(order['id'])
    >>> order['displayFulfillmentStatus']
    'PARTIALLY_FULFILLED'
    >>> len(order['fulfillments'])
    1
    >>> order['displayFinancialStatus']
    'PAID'

Ship and cancel remaining shipment::

    >>> shipment, = [s for s in sale.shipments if s.state != 'done']
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('ship')
    >>> shipment.state
    'shipped'

    >>> order = tools.get_order(order['id'])
    >>> order['displayFulfillmentStatus']
    'FULFILLED'
    >>> len(order['fulfillments'])
    2

    >>> shipment.click('cancel')
    >>> shipment.state
    'cancelled'

    >>> order = tools.get_order(order['id'])
    >>> order['displayFulfillmentStatus']
    'PARTIALLY_FULFILLED'
    >>> len(order['fulfillments'])
    2

    >>> shipment_exception = sale.click('handle_shipment_exception')
    >>> shipment_exception.form.recreate_moves.extend(
    ...     shipment_exception.form.ignore_moves.find())
    >>> shipment_exception.execute('handle')

Cancel remaining shipment::

    >>> shipment, = [s for s in sale.shipments if s.state not in {'done', 'cancelled'}]
    >>> shipment.click('cancel')
    >>> shipment.state
    'cancelled'

    >>> sale.reload()
    >>> sale.shipment_state
    'exception'
    >>> len(sale.invoices)
    0

    >>> order = tools.get_order(order['id'])
    >>> order['displayFulfillmentStatus']
    'PARTIALLY_FULFILLED'
    >>> len(order['fulfillments'])
    2
    >>> order['displayFinancialStatus']
    'PAID'

Ignore shipment exception::

    >>> shipment_exception = sale.click('handle_shipment_exception')
    >>> shipment_exception.form.ignore_moves.extend(
    ...     shipment_exception.form.ignore_moves.find())
    >>> shipment_exception.execute('handle')

    >>> order = tools.get_order(order['id'])
    >>> order['displayFulfillmentStatus']
    'FULFILLED'
    >>> len(order['fulfillments'])
    2
    >>> order['displayFinancialStatus']
    'PARTIALLY_REFUNDED'

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.total_amount
    Decimal('164.53')
    >>> payment, = sale.payments
    >>> payment.state
    'succeeded'

Correct taxes as partial invoice can get rounding gap::

    >>> tax_line, = invoice.taxes
    >>> tax_line.amount += payment.amount - invoice.total_amount
    >>> invoice.save()
    >>> assertEqual(invoice.total_amount, payment.amount)

Post invoice::

    >>> invoice.click('post')
    >>> invoice.state
    'paid'
    >>> sale.reload()
    >>> sale.state
    'done'
    >>> order = tools.get_order(order['id'])
    >>> bool(order['closed'])
    True

Clean up::

    >>> tools.delete_order(order['id'])
    >>> for product in ShopifyIdentifier.find(
    ...         [('record', 'like', 'product.template,%')]):
    ...     tools.delete_product(id2gid('Product', product.shopify_identifier))
    >>> for category in ShopifyIdentifier.find(
    ...         [('record', 'like', 'product.category,%')]):
    ...     tools.delete_collection(id2gid('Collection', category.shopify_identifier))
    >>> for _ in range(MAX_SLEEP):
    ...     try:
    ...         tools.delete_customer(customer['id'])
    ...     except Exception:
    ...         time.sleep(FETCH_SLEEP)
    ...     else:
    ...         break

    >>> shopify.ShopifyResource.clear_session()
