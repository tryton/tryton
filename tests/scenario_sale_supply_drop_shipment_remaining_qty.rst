==================================
Sale Supply Drop Shipment Scenario
==================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install sale_supply_drop_shipment, sale, purchase::

    >>> config = activate_modules([
    ...         'sale_supply_drop_shipment',
    ...         'sale',
    ...         'purchase',
    ...         ])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductSupplier = Model.get('purchase.product_supplier')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.supply_on_sale = True
    >>> template.save()
    >>> product, = template.products
    >>> product_supplier = ProductSupplier()
    >>> product_supplier.product = template
    >>> product_supplier.party = supplier
    >>> product_supplier.drop_shipment = True
    >>> product_supplier.lead_time = datetime.timedelta(0)
    >>> product_supplier.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale 250 products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 250
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')

Create Purchase from Request::

    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> purchase_request, = PurchaseRequest.find()
    >>> purchase_request.quantity
    250.0
    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [purchase_request])
    >>> purchase, = Purchase.find()
    >>> purchase.payment_term = payment_term
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> purchase.state
    u'processing'

    >>> sale.reload()
    >>> shipment, = sale.drop_shipments

The supplier sends more than expected::

    >>> move, = shipment.supplier_moves
    >>> move.quantity = 300
    >>> shipment.click('ship')

Another move has been created to synchronize supplier and customer quantities::

    >>> len(shipment.customer_moves)
    2
    >>> sum(m.quantity for m in shipment.customer_moves)
    300.0
