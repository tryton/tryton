============================
Sale Secondary Unit Scenario
============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts

Activate modules::

    >>> config = activate_modules(
    ...     ['sale_secondary_unit',
    ...     'account_invoice_secondary_unit',
    ...     'stock_secondary_unit'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

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
    >>> template.sale_secondary_uom_factor = 200
    >>> template.sale_secondary_uom_rate
    0.005
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

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
    'waiting'
    >>> sale.shipment_state
    'waiting'

Check secondary unit on invoice::

    >>> invoice, = sale.invoices
    >>> _, line = invoice.lines
    >>> line.secondary_unit == kg
    True
    >>> line.secondary_quantity
    2.0
    >>> line.secondary_unit_price
    Decimal('50.0000')

Check secondary unit on move::

    >>> move, = sale.moves
    >>> move.secondary_unit == kg
    True
    >>> move.secondary_quantity
    2.0
    >>> move.secondary_unit_price
    Decimal('50.0000')

    >>> shipment, = sale.shipments
    >>> move, = shipment.inventory_moves
    >>> move.secondary_unit == kg
    True
    >>> move.secondary_quantity
    2.0
