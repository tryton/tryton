=========================
Web Shop Shopify Scenario
=========================

Imports::

    >>> import datetime as dt
    >>> import os
    >>> import random
    >>> import string
    >>> import time
    >>> import urllib.request
    >>> from decimal import Decimal

    >>> import shopify
    >>> from shopify.api_version import ApiVersion

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts, create_tax)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

    >>> FETCH_SLEEP, MAX_SLEEP = 1, 10

Activate modules::

    >>> config = activate_modules([
    ...         'web_shop_shopify',
    ...         'account_payment_clearing',
    ...         'customs',
    ...         'product_measurements',
    ...         'product_image',
    ...         'sale_discount',
    ...         'sale_shipment_cost',
    ...         ])

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

    >>> from trytond.modules.web_shop_shopify.product import Template
    >>> def get_shopify_metafields(self, shop):
    ...     return {
    ...         'global.test': {
    ...             'value': self.name,
    ...             },
    ...         }

    >>> Template.get_shopify_metafields = get_shopify_metafields

    >>> from trytond.modules.web_shop_shopify.web import Shop
    >>> def managed_metafields(self):
    ...     return {'global.test'}

    >>> Shop.managed_metafields = managed_metafields

Create country::

    >>> belgium = Country(name="Belgium", code='BE')
    >>> belgium.save()
    >>> china = Country(name="China", code='CN')
    >>> china.save()

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create tax::

    >>> tax = create_tax(Decimal('.10'))

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
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

    >>> location = shopify.Location.find_first()

    >>> shop_warehouse, = web_shop.shopify_warehouses
    >>> shop_warehouse.shopify_id = str(location.id)
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
    >>> image.image = urllib.request.urlopen('https://picsum.photos/200').read()
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
    >>> image.image = urllib.request.urlopen('https://picsum.photos/200').read()
    >>> variant1.save()

    >>> image = variant2.images.new(web_shop=True, template=variant)
    >>> image.image = urllib.request.urlopen('https://picsum.photos/200').read()
    >>> variant2.save()

Create carrier::

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

    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()

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
    ...     inventory_levels = location.inventory_levels()
    ...     if inventory_levels and len(inventory_levels) == 2:
    ...         break
    ...     time.sleep(FETCH_SLEEP)
    >>> sorted(l.available for l in inventory_levels
    ...     if l.available and l.inventory_item_id in inventory_item_ids)
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
    >>> len(product2.template.shopify_identifiers)
    0
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

    >>> customer = shopify.Customer()
    >>> customer.last_name = "Customer"
    >>> customer.email = (
    ...     ''.join(random.choice(string.ascii_letters) for _ in range(10))
    ...     + '@example.com')
    >>> customer.addresses = [{
    ...         'address1': "Street",
    ...         'city': "City",
    ...         'country': "Belgium",
    ...         }]
    >>> customer.save()
    True

    >>> order = shopify.Order.create({
    ...     'customer': customer.to_dict(),
    ...     'shipping_address': customer.addresses[0].to_dict(),
    ...     'billing_address': customer.addresses[0].to_dict(),
    ...     'line_items': [{
    ...         'variant_id': product1.shopify_identifiers[0].shopify_identifier,
    ...         'quantity': 1,
    ...         }, {
    ...         'variant_id': product1.shopify_identifiers[0].shopify_identifier,
    ...         'quantity': 1,
    ...         }, {
    ...         'variant_id': variant1.shopify_identifiers[0].shopify_identifier,
    ...         'quantity': 5,
    ...         }],
    ...     'financial_status': 'authorized',
    ...     'transactions': [{
    ...         'kind': 'authorization',
    ...         'status': 'success',
    ...         'amount': '258.98',
    ...         'test': True,
    ...         }],
    ...     'discount_codes': [{
    ...         'code': 'CODE',
    ...         'amount': '15',
    ...         'type': 'fixed_amount',
    ...         }],
    ...     'shipping_lines': [{
    ...         'code': 'SHIP',
    ...         'title': "Shipping",
    ...         'price': '4.00',
    ...         }],
    ...     })
    >>> order.total_price
    '258.98'
    >>> order.financial_status
    'authorized'
    >>> order.fulfillment_status

Run fetch order::

    >>> with config.set_context(shopify_orders=order.id):
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
    >>> sale.total_amount
    Decimal('258.98')
    >>> len(sale.payments)
    1
    >>> payment, = sale.payments
    >>> payment.state
    'processing'
    >>> payment.amount
    Decimal('258.98')
    >>> sale.carrier == carrier
    True
    >>> sale.state
    'quotation'

Capture full amount::

    >>> transaction = order.capture('258.98')
    >>> test_transaction_id = transaction.parent_id

    >>> with config.set_context(shopify_orders=order.id):
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

Make a partial shipment::

    >>> shipment, = sale.shipments
    >>> move, = [m for m in shipment.inventory_moves if m.product == variant1]
    >>> move.quantity = 3
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.state
    'done'

    >>> sale.reload()
    >>> len(sale.invoices)
    0

    >>> order.reload()
    >>> order.fulfillment_status
    'partial'
    >>> len(order.fulfillments)
    1
    >>> order.financial_status
    'paid'

Cancel remaining shipment::

    >>> shipment, = [s for s in sale.shipments if s.state != 'done']
    >>> shipment.click('cancel')
    >>> shipment.state
    'cancelled'

    >>> sale.reload()
    >>> sale.shipment_state
    'exception'
    >>> len(sale.invoices)
    0

    >>> order.reload()
    >>> order.fulfillment_status
    'partial'
    >>> len(order.fulfillments)
    1
    >>> order.financial_status
    'paid'

Ignore shipment exception::

    >>> shipment_exception = sale.click('handle_shipment_exception')
    >>> move = shipment_exception.form.recreate_moves.pop()
    >>> shipment_exception.execute('handle')

    >>> order.reload()
    >>> order.fulfillment_status
    'fulfilled'
    >>> len(order.fulfillments)
    1
    >>> order.financial_status
    'partially_refunded'

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.total_amount
    Decimal('164.52')
    >>> payment, = sale.payments
    >>> payment.state
    'succeeded'

Correct taxes as partial invoice can get rounding gap::

    >>> tax_line, = invoice.taxes
    >>> tax_line.amount += payment.amount - invoice.total_amount
    >>> invoice.save()
    >>> invoice.total_amount == payment.amount
    True

Post invoice::

    >>> invoice.click('post')
    >>> invoice.state
    'paid'
    >>> sale.reload()
    >>> sale.state
    'done'
    >>> order.reload()
    >>> bool(order.closed_at)
    True

Clean up::

    >>> order.destroy()
    >>> for product in ShopifyIdentifier.find(
    ...         [('record', 'like', 'product.template,%')]):
    ...     shopify.Product.find(product.shopify_identifier).destroy()
    >>> for category in ShopifyIdentifier.find(
    ...         [('record', 'like', 'product.category,%')]):
    ...     shopify.CustomCollection.find(category.shopify_identifier).destroy()
    >>> time.sleep(FETCH_SLEEP)
    >>> customer.destroy()

    >>> shopify.ShopifyResource.clear_session()
