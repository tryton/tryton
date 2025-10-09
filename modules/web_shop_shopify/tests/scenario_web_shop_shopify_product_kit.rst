=====================================
Web Shop Shopify Product Kit Scenario
=====================================

Imports::

    >>> import os
    >>> import random
    >>> import string
    >>> import time
    >>> from decimal import Decimal

    >>> import shopify
    >>> from shopify.api_version import ApiVersion

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.web_shop_shopify.common import gid2id, id2gid
    >>> from trytond.modules.web_shop_shopify.tests import tools
    >>> from trytond.tests.tools import activate_modules

    >>> FETCH_SLEEP, MAX_SLEEP = 1, 10

Activate modules::

    >>> config = activate_modules([
    ...         'web_shop_shopify',
    ...         'product_kit',
    ...         ],
    ...     create_company, create_chart)

    >>> Account = Model.get('account.account')
    >>> Category = Model.get('product.category')
    >>> Cron = Model.get('ir.cron')
    >>> Location = Model.get('stock.location')
    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> Product = Model.get('product.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> Sale = Model.get('sale.sale')
    >>> ShopifyIdentifier = Model.get('web.shop.shopify_identifier')
    >>> Uom = Model.get('product.uom')
    >>> WebShop = Model.get('web.shop')

Get company::

    >>> company = get_company()

Get accounts::

    >>> accounts = get_accounts()

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

    >>> category = Category(name="Category")
    >>> category.save()

    >>> account_category = Category(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product kit::

    >>> unit, = Uom.find([('name', '=', "Unit")])
    >>> meter, = Uom.find([('name', '=', "Meter")])

    >>> template = ProductTemplate()
    >>> template.name = "Component 1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> component1, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Component 2"
    >>> template.default_uom = meter
    >>> template.type = 'goods'
    >>> template.save()
    >>> component2, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Product Kit"
    >>> template.default_uom = unit
    >>> template.type = 'kit'
    >>> template.salable = True
    >>> template.list_price = Decimal('100.0000')
    >>> template.account_category = account_category
    >>> template.categories.append(Category(category.id))
    >>> template.save()
    >>> product, = template.products
    >>> product.suffix_code = 'PROD'
    >>> product.save()

    >>> _ = template.components.new(product=component1, quantity=2)
    >>> _ = template.components.new(product=component2, quantity=5)
    >>> template.save()

Set categories, products and attributes to web shop::

    >>> web_shop.categories.append(Category(category.id))
    >>> web_shop.products.append(Product(product.id))
    >>> web_shop.save()

Run update product::

    >>> cron_update_product, = Cron.find([
    ...     ('method', '=', 'web.shop|shopify_update_product'),
    ...     ])
    >>> cron_update_product.click('run_once')

Create an order on Shopify::

    >>> customer = tools.create_customer({
    ...         'lastName': "Customer",
    ...         'email': (''.join(
    ...                 random.choice(string.ascii_letters) for _ in range(10))
    ...             + '@example.com'),
    ...         'addresses': [{
    ...                 'address1': "Street",
    ...                 'city': "City",
    ...                 'countryCode': 'BE',
    ...                 }],
    ...         })

    >>> order = tools.create_order({
    ...         'customerId': customer['id'],
    ...         'lineItems': [{
    ...             'variantId': id2gid(
    ...                 'ProductVariant',
    ...                 product.shopify_identifiers[0].shopify_identifier),
    ...             'quantity': 3,
    ...             }],
    ...         'financialStatus': 'AUTHORIZED',
    ...         'transactions': [{
    ...             'kind': 'AUTHORIZATION',
    ...             'status': 'SUCCESS',
    ...             'amountSet': {
    ...                 'shopMoney': {
    ...                     'amount': 300,
    ...                     'currencyCode': company.currency.code,
    ...                     },
    ...                 },
    ...             'test': True,
    ...             }],
    ...         })
    >>> order['totalPriceSet']['presentmentMoney']['amount']
    '300.0'
    >>> order['displayFinancialStatus']
    'AUTHORIZED'

    >>> transaction = tools.capture_order(
    ...     order['id'], 300, order['transactions'][0]['id'])

Run fetch order::

    >>> with config.set_context(shopify_orders=[gid2id(order['id'])]):
    ...     cron_fetch_order, = Cron.find([
    ...         ('method', '=', 'web.shop|shopify_fetch_order'),
    ...         ])
    ...     for _ in range(MAX_SLEEP):
    ...         cron_fetch_order.click('run_once')
    ...         if Sale.find([]):
    ...             break
    ...         time.sleep(FETCH_SLEEP)

    >>> sale, = Sale.find([])
    >>> sale.total_amount
    Decimal('300.00')
    >>> sale_line, = sale.lines
    >>> sale_line.quantity
    3.0

Make a partial shipment of components::

    >>> shipment, = sale.shipments
    >>> for move in shipment.inventory_moves:
    ...     if move.product == component1:
    ...         move.quantity = 4
    ...     else:
    ...         move.quantity = 0
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> order = tools.get_order(order['id'])
    >>> order['displayFulfillmentStatus']
    'PARTIALLY_FULFILLED'
    >>> fulfillment, = order['fulfillments']
    >>> fulfillment_line_item, = fulfillment['fulfillmentLineItems']['nodes']
    >>> fulfillment_line_item['quantity']
    2

Make a partial shipment for a single component::

    >>> sale.reload()
    >>> _, shipment = sale.shipments
    >>> for move in shipment.inventory_moves:
    ...     if move.product == component1:
    ...         move.quantity = 0
    ...     else:
    ...         move.quantity = 10
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> order = tools.get_order(order['id'])
    >>> order['displayFulfillmentStatus']
    'PARTIALLY_FULFILLED'
    >>> fulfillment, = order['fulfillments']
    >>> fulfillment_line_item, = fulfillment['fulfillmentLineItems']['nodes']
    >>> fulfillment_line_item['quantity']
    2

Ship remaining::

    >>> sale.reload()
    >>> _, _, shipment = sale.shipments
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> order = tools.get_order(order['id'])
    >>> order['displayFulfillmentStatus']
    'FULFILLED'

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
