==============================
Purchase Receive Other Product
==============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Install purchase::

    >>> config = activate_modules('purchase')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_expense = expense
    >>> product, = template.products
    >>> product.cost_price = Decimal('5')
    >>> product = template.products.new()
    >>> product.cost_price = Decimal('5')
    >>> template.save()
    >>> product1, product2 = template.products
    >>> product1.code = '1'
    >>> product1.save()
    >>> product2.code = '2'
    >>> product2.save()

Purchase 5 products::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.invoice_method = 'shipment'
    >>> line = purchase.lines.new()
    >>> line.product = product1
    >>> line.quantity = 5
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')

Replace 2 produces and receive::

    >>> incoming_move1, = purchase.moves
    >>> incoming_move1.quantity = 3
    >>> incoming_move1.save()
    >>> incoming_move2, = incoming_move1.duplicate()
    >>> incoming_move2.quantity = 2
    >>> incoming_move2.product = product2
    >>> incoming_move2.save()

    >>> Move = Model.get('stock.move')
    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> shipment.incoming_moves.append(Move(incoming_move1.id))
    >>> shipment.incoming_moves.append(Move(incoming_move2.id))
    >>> shipment.save()
    >>> shipment.click('receive')
    >>> shipment.click('done')

Check invoice has 2 products::

    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> len(invoice.lines)
    2
    >>> line1, = [l for l in invoice.lines if l.product == product1]
    >>> line2, = [l for l in invoice.lines if l.product == product2]

    >>> line1.quantity
    3.0
    >>> line1.stock_moves == [incoming_move1]
    True

    >>> line2.quantity
    2.0
    >>> line2.stock_moves == [incoming_move2]
    True
