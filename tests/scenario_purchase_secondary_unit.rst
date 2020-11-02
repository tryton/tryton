================================
Purchase Secondary Unit Scenario
================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts

Activate modules::

    >>> config = activate_modules([
    ...         'purchase_secondary_unit',
    ...         'account_invoice_secondary_unit',
    ...         'stock_secondary_unit'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

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
    >>> template.purchasable = True
    >>> template.purchase_secondary_uom = gr
    >>> template.purchase_secondary_uom_factor = 100
    >>> template.purchase_secondary_uom_rate
    0.01
    >>> product_supplier = template.product_suppliers.new()
    >>> product_supplier.party = supplier
    >>> product_supplier.purchase_secondary_uom = gr
    >>> product_supplier.purchase_secondary_uom_factor = 200
    >>> product_supplier.purchase_secondary_uom_rate
    0.005
    >>> price = product_supplier.prices.new()
    >>> price.quantity = 0
    >>> price.unit_price = Decimal('3')
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products
    >>> product_supplier, = template.product_suppliers

Purchase product::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> line = purchase.lines.new()
    >>> line.type = 'comment'
    >>> line.description = 'Comment'
    >>> line = purchase.lines.new()
    >>> line.product = product
    >>> line.quantity = 10

Check secondary unit::

    >>> line.product_supplier = product_supplier
    >>> line.quantity = 10

    >>> line.secondary_unit = kg
    >>> line.secondary_quantity
    2.0
    >>> line.secondary_unit_price
    Decimal('15.0000')
    >>> line.secondary_unit_price = Decimal('20')
    >>> line.unit_price
    Decimal('4.0000')
    >>> line.secondary_quantity = 2000
    >>> line.quantity
    10000.0
    >>> line.secondary_unit = gr
    >>> line.quantity
    10.0

Confirm purchase::

    >>> line.secondary_unit = kg
    >>> line.quantity = 10
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.invoice_state
    'waiting'
    >>> purchase.shipment_state
    'waiting'

Check secondary unit on invoice::

    >>> invoice, = purchase.invoices
    >>> _, line = invoice.lines
    >>> line.secondary_unit == kg
    True
    >>> line.secondary_quantity
    2.0
    >>> line.secondary_unit_price
    Decimal('15.0000')

Check secondary unit on move::

    >>> move, = purchase.moves
    >>> move.secondary_unit == kg
    True
    >>> move.secondary_quantity
    2.0
    >>> move.secondary_unit_price
    Decimal('15.0000')
