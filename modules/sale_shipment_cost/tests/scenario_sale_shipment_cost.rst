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

Install sale_shipment_cost, sale and account_invoice::

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
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.lead_time = datetime.timedelta(0)
    >>> carrier_template.list_price = Decimal('3')
    >>> carrier_template.account_revenue = revenue
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products

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
    u'processing'
    >>> sale.untaxed_amount
    Decimal('103.00')

Send products::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment, = sale.shipments
    >>> shipment.carrier == carrier
    True
    >>> shipment.cost
    Decimal('3.0000')
    >>> shipment.cost_currency == company.currency
    True
    >>> move, = shipment.inventory_moves
    >>> move.quantity = 4
    >>> shipment.cost
    Decimal('3.0000')
    >>> shipment.cost_currency == company.currency
    True
    >>> shipment.state
    u'waiting'
    >>> shipment.click('assign_force')
    >>> shipment.state
    u'assigned'
    >>> shipment.click('pack')
    >>> shipment.state
    u'packed'
    >>> shipment.click('done')
    >>> shipment.state
    u'done'

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> sorted([l.product.id for l in invoice.lines]) == \
    ...     sorted([product.id, carrier_product.id])
    True
    >>> invoice.untaxed_amount
    Decimal('83.00')

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
    u'processing'
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
