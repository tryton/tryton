============================
Sale Secondary Unit Scenario
============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules([
    ...     'sale_amendment',
    ...     'sale_product_customer',
    ...     'sale_secondary_unit',
    ...     'account_invoice_secondary_unit',
    ...     'stock_secondary_unit'],
    ...     create_company, create_chart)

Create chart of accounts::

    >>> accounts = get_accounts()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create account categories::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> gr, = ProductUom.find([('name', '=', "Gram")])
    >>> kg, = ProductUom.find([('name', '=', "Kilogram")])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.sale_secondary_uom = gr
    >>> template.sale_secondary_uom_factor = 100
    >>> template.sale_secondary_uom_rate
    0.01
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products
    >>> product_customer = product.product_customers.new()
    >>> product_customer.party = customer
    >>> product_customer.sale_secondary_uom = gr
    >>> product_customer.sale_secondary_uom_factor = 200
    >>> product_customer.sale_secondary_uom_rate
    0.005
    >>> product.save()

Sale product::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.type = 'comment'
    >>> line.description = 'Comment'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10

Check secondary unit::

    >>> assertEqual(line.secondary_unit, gr)
    >>> line.secondary_quantity
    2000.0
    >>> line.secondary_quantity = None
    >>> line.secondary_unit = kg
    >>> line.secondary_quantity
    2.0
    >>> line.secondary_unit_price
    Decimal('50.0000')
    >>> line.secondary_unit_price = Decimal('40')
    >>> line.unit_price
    Decimal('8.0000')
    >>> line.secondary_quantity = 1000
    >>> line.quantity
    5000.0
    >>> line.secondary_unit = gr
    >>> line.quantity
    5.0

Confirm sale::

    >>> line.secondary_unit = kg
    >>> line.quantity = 10
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.invoice_state
    'pending'
    >>> sale.shipment_state
    'waiting'

Check secondary unit on invoice::

    >>> invoice, = sale.invoices
    >>> line, = invoice.lines
    >>> assertEqual(line.secondary_unit, kg)
    >>> line.secondary_quantity
    2.0
    >>> line.secondary_unit_price
    Decimal('50.0000')

Check secondary unit on move::

    >>> move, = sale.moves
    >>> assertEqual(move.secondary_unit, kg)
    >>> move.secondary_quantity
    2.0
    >>> move.secondary_unit_price
    Decimal('50.0000')

    >>> shipment, = sale.shipments
    >>> move, = shipment.inventory_moves
    >>> assertEqual(move.secondary_unit, kg)
    >>> move.secondary_quantity
    2.0

Add an amendment::

    >>> amendment = sale.amendments.new()
    >>> line = amendment.lines.new()
    >>> line.action = 'line'
    >>> line.line = sale.lines[-1]
    >>> line.quantity = 1
    >>> line.unit = kg
    >>> line.unit_price = Decimal('45.0000')
    >>> amendment.click('validate_amendment')

    >>> sale.reload()
    >>> line = sale.lines[-1]
    >>> line.quantity
    5.0
    >>> line.secondary_quantity
    1.0
    >>> line.unit_price
    Decimal('9.0000')
    >>> line.secondary_unit_price
    Decimal('45.0000')
