================================
Sale Ship Other Product Scenario
================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Install sale::

    >>> config = activate_modules('sale')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_revenue = revenue
    >>> product = template.products.new()
    >>> template.save()
    >>> product1, product2 = template.products
    >>> product1.code = '1'
    >>> product1.save()
    >>> product2.code = '2'
    >>> product2.save()

Sale 5 products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.invoice_method = 'shipment'
    >>> line = sale.lines.new()
    >>> line.product = product1
    >>> line.quantity = 5
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')

Replace 2 products and ship::

    >>> shipment, = sale.shipments
    >>> shipment.click('draft')
    >>> outgoing_move1, = shipment.outgoing_moves
    >>> outgoing_move1.quantity = 3
    >>> outgoing_move1.save()
    >>> outgoing_move2, = outgoing_move1.duplicate()
    >>> outgoing_move2.quantity = 2
    >>> outgoing_move2.product = product2
    >>> outgoing_move2.save()

    >>> shipment.click('wait')
    >>> shipment.click('assign_force')
    >>> shipment.click('pack')
    >>> shipment.click('done')

Check invoice has 2 products::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> len(invoice.lines)
    2
    >>> line1, = [l for l in invoice.lines if l.product == product1]
    >>> line2, = [l for l in invoice.lines if l.product == product2]

    >>> line1.quantity
    3.0
    >>> line1.stock_moves == [outgoing_move1]
    True

    >>> line2.quantity
    2.0
    >>> line2.stock_moves == [outgoing_move2]
    True
