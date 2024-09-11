==========================
Stock Consignment Scenario
==========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_tax, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('stock_consignment', create_company, create_chart)

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create tax::

    >>> supplier_tax = create_tax(Decimal('.10'))
    >>> supplier_tax.save()
    >>> customer_tax = create_tax(Decimal('.10'))
    >>> customer_tax.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])

Create supplier consignment location::

    >>> supplier_consignment_loc = Location()
    >>> supplier_consignment_loc.name = "Supplier Consignment"
    >>> supplier_consignment_loc.type = 'supplier'
    >>> supplier_consignment_loc.parent = storage_loc
    >>> supplier_consignment_loc.consignment_party = supplier
    >>> supplier_consignment_loc.save()

Create customer consignment location::

    >>> customer_consignment_loc = Location()
    >>> customer_consignment_loc.name = "Customer Consignment"
    >>> customer_consignment_loc.type = 'storage'
    >>> customer_consignment_loc.parent = customer_loc
    >>> customer_consignment_loc.consignment_party = customer
    >>> customer_consignment_loc.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.supplier_taxes.append(supplier_tax)
    >>> account_category.customer_taxes.append(customer_tax)
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> product_supplier = template.product_suppliers.new()
    >>> product_supplier.party = supplier
    >>> price = product_supplier.prices.new()
    >>> price.quantity = 1
    >>> price.unit_price = Decimal('5')
    >>> price = product_supplier.prices.new()
    >>> price.quantity = 2
    >>> price.unit_price = Decimal('4')
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Fill supplier consignment location::

    >>> Shipment = Model.get('stock.shipment.internal')
    >>> shipment = Shipment()
    >>> shipment.from_location = supplier_loc
    >>> shipment.to_location = supplier_consignment_loc
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = supplier_loc
    >>> move.to_location = supplier_consignment_loc
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> shipment.click('assign_try')
    >>> shipment.state
    'assigned'
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Use supplier consignment stock::

    >>> shipment = Shipment()
    >>> shipment.from_location = supplier_consignment_loc
    >>> shipment.to_location = storage_loc
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 4
    >>> move.from_location = supplier_consignment_loc
    >>> move.to_location = storage_loc
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> shipment.click('assign_try')
    >>> shipment.state
    'assigned'
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Check supplier invoice line::

    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> invoice_line, = InvoiceLine.find([('invoice_type', '=', 'in')])
    >>> assertEqual(invoice_line.product, product)
    >>> invoice_line.quantity
    4.0
    >>> assertEqual(invoice_line.unit, unit)
    >>> invoice_line.unit_price
    Decimal('4.0000')
    >>> assertEqual(invoice_line.taxes, [supplier_tax])
    >>> move, = shipment.moves
    >>> assertEqual(move.origin, invoice_line)

Use supplier consignment stock for shipment out::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc
    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 3
    >>> move.unit_price = Decimal('10')
    >>> move.currency = shipment_out.company.currency
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> shipment_out.click('wait')
    >>> move, = shipment_out.inventory_moves
    >>> move.from_location = supplier_consignment_loc
    >>> shipment_out.click('assign_try')
    >>> shipment_out.state
    'assigned'
    >>> move, = shipment_out.inventory_moves
    >>> len(move.invoice_lines)
    1

Fill customer consignment location::

    >>> shipment = Shipment()
    >>> shipment.from_location = storage_loc
    >>> shipment.to_location = customer_consignment_loc
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 3
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_consignment_loc
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> shipment.click('assign_try')
    >>> shipment.state
    'assigned'
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Use customer consignment stock::

    >>> shipment = Shipment()
    >>> shipment.from_location = customer_consignment_loc
    >>> shipment.to_location = customer_loc
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = customer_consignment_loc
    >>> move.to_location = customer_loc
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> shipment.click('assign_try')
    >>> shipment.state
    'assigned'
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Check customer invoice line::

    >>> invoice_line, = InvoiceLine.find([('invoice_type', '=', 'out')])
    >>> assertEqual(invoice_line.product, product)
    >>> invoice_line.quantity
    1.0
    >>> assertEqual(invoice_line.unit, unit)
    >>> invoice_line.unit_price
    Decimal('10.0000')
    >>> assertEqual(invoice_line.taxes, [customer_tax])
    >>> move, = shipment.moves
    >>> assertEqual(move.origin, invoice_line)

Duplicate shipment clear origin::

    >>> duplicate, = shipment.duplicate()
    >>> move, = duplicate.moves
    >>> move.origin

Cancel supplier consignment stock::

    >>> shipment = Shipment()
    >>> shipment.from_location = supplier_consignment_loc
    >>> shipment.to_location = storage_loc
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = supplier_consignment_loc
    >>> move.to_location = storage_loc
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> shipment.click('assign_try')
    >>> shipment.state
    'assigned'
    >>> move, = shipment.moves
    >>> bool(move.origin)
    True
    >>> shipment.click('cancel')
    >>> shipment.state
    'cancelled'
    >>> move, = shipment.moves
    >>> bool(move.origin)
    False
