===========================
Sale Shipment Cost Scenario
===========================

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

Activate modules::

    >>> config = activate_modules([
    ...         'sale_shipment_cost',
    ...         'sale',
    ...         'account_invoice',
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

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.lead_time = datetime.timedelta(0)
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.lead_time = datetime.timedelta(0)
    >>> carrier_template.list_price = Decimal('3')
    >>> carrier_template.account_category = account_category
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products
    >>> carrier_product.cost_price = Decimal('2')
    >>> carrier_product.save()

Create carrier::

    >>> Carrier = Model.get('carrier')
    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()

Use it as the default carrier::

    >>> CarrierSelection = Model.get('carrier.selection')
    >>> csc = CarrierSelection(carrier=carrier)
    >>> csc.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale products with cost on shipment::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'shipment'
    >>> sale.shipment_cost_method = 'shipment'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> cost_line = sale.lines[-1]
    >>> cost_line.product == carrier_product
    True
    >>> cost_line.quantity
    1.0
    >>> cost_line.amount
    Decimal('3.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'
    >>> sale.untaxed_amount
    Decimal('103.00')

Send products::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment, = sale.shipments
    >>> shipment.carrier == carrier
    True
    >>> shipment.cost_used
    Decimal('2.0000')
    >>> shipment.cost_sale_used
    Decimal('3.0000')
    >>> shipment.cost_sale_currency_used == company.currency
    True
    >>> move, = shipment.inventory_moves
    >>> move.quantity = 4
    >>> shipment.cost_sale_used
    Decimal('3.0000')
    >>> shipment.cost_sale_currency_used == company.currency
    True
    >>> shipment.state
    'waiting'
    >>> shipment.click('assign_force')
    >>> shipment.state
    'assigned'
    >>> shipment.click('pick')
    >>> shipment.state
    'picked'
    >>> shipment.click('pack')
    >>> shipment.state
    'packed'
    >>> shipment.click('done')
    >>> shipment.state
    'done'

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> sorted([l.product.id for l in invoice.lines]) == \
    ...     sorted([product.id, carrier_product.id])
    True
    >>> invoice.untaxed_amount
    Decimal('83.00')

Send missing products::

    >>> sale.reload()
    >>> shipment, = [s for s in sale.shipments if s.state == 'waiting']
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> sale.reload()
    >>> len(sale.invoices)
    2
    >>> new_invoice, = [i for i in sale.invoices if i != invoice]
    >>> new_invoice.untaxed_amount
    Decimal('23.00')

Sale products with cost on order::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale.shipment_cost_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3.0
    >>> sale.click('quote')
    >>> cost_line = sale.lines[-1]
    >>> cost_line.product == carrier_product
    True
    >>> cost_line.quantity
    1.0
    >>> cost_line.amount
    Decimal('3.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'
    >>> sale.untaxed_amount
    Decimal('63.00')

Check customer shipment::

    >>> shipment, = sale.shipments
    >>> shipment.carrier == carrier
    True

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.untaxed_amount
    Decimal('63.00')

Return the sale::

    >>> return_sale = Wizard('sale.return_sale', [sale])
    >>> return_sale.execute('return_')
    >>> returned_sale, = Sale.find([
    ...     ('state', '=', 'draft'),
    ...     ])
    >>> returned_sale.untaxed_amount
    Decimal('-63.00')

The quotation of the returned sale does not change the amount::

    >>> returned_sale.click('quote')
    >>> returned_sale.untaxed_amount
    Decimal('-63.00')

Sale products with cost on order and invoice method on shipment::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'shipment'
    >>> sale.shipment_cost_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

Check no customer invoice::

    >>> len(sale.invoices)
    0

Send products::

    >>> shipment, = sale.shipments
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.state
    'done'

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> len(invoice.lines)
    2

Sale products with no cost::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'shipment'
    >>> sale.shipment_cost_method = None
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1.0
    >>> sale.click('quote')
    >>> len(sale.lines)
    1
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

Check no customer invoice::

    >>> len(sale.invoices)
    0

Send products::

    >>> shipment, = sale.shipments
    >>> shipment.cost_used
    Decimal('2.0000')
    >>> shipment.cost_sale_used
    Decimal('3.0000')
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.state
    'done'

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> len(invoice.lines)
    1
