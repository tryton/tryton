==================================================
Purchase Shipment Cost with Invoice Stock Scenario
==================================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules([
    ...         'purchase_shipment_cost',
    ...         'account_invoice_stock',
    ...         'purchase',
    ...         ])

    >>> Carrier = Model.get('carrier')
    >>> Move = Model.get('stock.move')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Purchase = Model.get('purchase.purchase')
    >>> ShipmentIn = Model.get('stock.shipment.in')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create account categories::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.save()

Create supplier::

    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create products::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.list_price = Decimal('5')
    >>> carrier_product, = carrier_template.products
    >>> carrier_product.cost_price = Decimal('3')
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products

Create carrier::

    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()

Purchase a product::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> line = purchase.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('10')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

Receive the product::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> move, = purchase.moves
    >>> shipment.incoming_moves.append(Move(id=move.id))
    >>> shipment.carrier = carrier
    >>> shipment.cost_used
    Decimal('3.0000')
    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> move, = shipment.incoming_moves
    >>> move.unit_price
    Decimal('13.0000')

Post the invoice with a different price::

    >>> invoice, = purchase.invoices
    >>> line, = invoice.lines
    >>> line.unit_price = Decimal('9')
    >>> invoice.invoice_date = today
    >>> invoice.click('post')

Check unit price of move::

    >>> move.reload()
    >>> move.unit_price
    Decimal('12.0000')
