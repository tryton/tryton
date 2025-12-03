=================================================
Sale Shipment Cost Cancelled On Shipment Scenario
=================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules([
    ...         'sale_shipment_cost',
    ...         ],
    ...     create_company, create_chart)

    >>> Carrier = Model.get('carrier')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

Get accounts::

    >>> accounts = get_accounts()

Create customer::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = "Carrier Product"
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.list_price = Decimal('3')
    >>> carrier_template.account_category = account_category
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products
    >>> carrier_product.cost_price = Decimal('2')
    >>> carrier_product.save()

Create carrier::

    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()

Sale products with cost on shipment::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.invoice_method = 'shipment'
    >>> sale.shipment_cost_method = 'shipment'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

Ship products::

    >>> shipment, = sale.shipments
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Cancel customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.untaxed_amount
    Decimal('103.00')
    >>> invoice.click('cancel')
    >>> invoice.state
    'cancelled'

    >>> sale.reload()
    >>> sale.invoice_state
    'exception'

Recreate invoice::

    >>> invoice_handle_exception = sale.click('handle_invoice_exception')
    >>> invoice_handle_exception.form.recreate_invoices.extend(
    ...     invoice_handle_exception.form.recreate_invoices.find())
    >>> invoice_handle_exception.execute('handle')

    >>> sale.invoice_state
    'pending'
    >>> _, invoice = sale.invoices
    >>> invoice.untaxed_amount
    Decimal('103.00')
