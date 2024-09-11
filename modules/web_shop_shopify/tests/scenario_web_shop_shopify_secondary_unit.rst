========================================
Web Shop Shopify Secondary Unit Scenario
========================================

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
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> FETCH_SLEEP, MAX_SLEEP = 1, 10

Activate modules::

    >>> config = activate_modules([
    ...         'web_shop_shopify',
    ...         'sale_secondary_unit',
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

    >>> location = shopify.Location.find_first()

    >>> shop_warehouse, = web_shop.shopify_warehouses
    >>> shop_warehouse.shopify_id = str(location.id)
    >>> web_shop.save()

Create categories::

    >>> category = Category(name="Category")
    >>> category.save()

    >>> account_category = Category(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = Uom.find([('name', '=', "Unit")])
    >>> unit.digits = 2
    >>> unit.rounding = 0.01
    >>> unit.save()
    >>> cm, = Uom.find([('name', '=', "Centimeter")])
    >>> cm, = cm.duplicate(default={'digits': 0, 'rounding': 1})

    >>> template = ProductTemplate()
    >>> template.name = "Product 1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.sale_secondary_uom = cm
    >>> template.sale_secondary_uom_factor = 25
    >>> template.list_price = Decimal('100.0000')
    >>> template.account_category = account_category
    >>> template.categories.append(Category(category.id))
    >>> template.save()
    >>> product, = template.products
    >>> product.suffix_code = 'PROD'
    >>> product.save()

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

    >>> customer = shopify.Customer()
    >>> customer.last_name = "Customer"
    >>> customer.email = (
    ...     ''.join(random.choice(string.ascii_letters) for _ in range(10))
    ...     + '@example.com')
    >>> customer.addresses = [{
    ...         'address1': "Street",
    ...         'city': "City",
    ...         }]
    >>> customer.save()
    True

    >>> order = shopify.Order.create({
    ...     'customer': customer.to_dict(),
    ...     'shipping_address': customer.addresses[0].to_dict(),
    ...     'billing_address': customer.addresses[0].to_dict(),
    ...     'line_items': [{
    ...         'variant_id': product.shopify_identifiers[0].shopify_identifier,
    ...         'quantity': 50,
    ...         }],
    ...     'financial_status': 'authorized',
    ...     'transactions': [{
    ...         'kind': 'authorization',
    ...         'status': 'success',
    ...         'amount': '202.00',
    ...         'test': True,
    ...         }],
    ...     'shipping_lines': [{
    ...         'code': 'SHIP',
    ...         'title': "Shipping",
    ...         'price': '2.00',
    ...         }],
    ...     })
    >>> order.total_price
    '202.00'
    >>> order.financial_status
    'authorized'

Run fetch order::

    >>> with config.set_context(shopify_orders=order.id):
    ...     cron_fetch_order, = Cron.find([
    ...         ('method', '=', 'web.shop|shopify_fetch_order'),
    ...         ])
    ...     for _ in range(MAX_SLEEP):
    ...         cron_fetch_order.click('run_once')
    ...         if Sale.find([]):
    ...             break
    ...         time.sleep(FETCH_SLEEP)

    >>> sale, = Sale.find([])
    >>> len(sale.lines)
    2
    >>> sale.total_amount
    Decimal('202.00')
    >>> line, = [l for l in sale.lines if l.product]
    >>> line.quantity
    2.0
    >>> assertEqual(line.unit, unit)
    >>> line.unit_price
    Decimal('100.0000')
    >>> line.secondary_quantity
    50.0
    >>> assertEqual(line.secondary_unit, cm)
    >>> line.secondary_unit_price
    Decimal('4.0000')

Clean up::

    >>> order.destroy()
    >>> for product in ShopifyIdentifier.find(
    ...         [('record', 'like', 'product.template,%')]):
    ...     shopify.Product.find(product.shopify_identifier).destroy()
    >>> for category in ShopifyIdentifier.find(
    ...         [('record', 'like', 'product.category,%')]):
    ...     shopify.CustomCollection.find(category.shopify_identifier).destroy()
    >>> time.sleep(2)
    >>> customer.destroy()

    >>> shopify.ShopifyResource.clear_session()
