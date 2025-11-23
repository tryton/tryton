====================
Sale Rental Scenario
====================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_tax, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today() - dt.timedelta(days=20)
    >>> now = dt.datetime.combine(today, dt.time(8))

Activate modules::

    >>> config = activate_modules('sale_rental', create_company, create_chart)

    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Rental = Model.get('sale.rental')

Get accounts::

    >>> accounts = get_accounts()

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create account category::

    >>> account_category = ProductCategory(name="Account")
    >>> account_category.accounting = True
    >>> account_category.account_rental = accounts['revenue']
    >>> account_category.customer_rental_taxes.append(tax)
    >>> account_category.save()

Create a rentable asset::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> day, = ProductUom.find([('name', '=', "Day")])
    >>> hour, = ProductUom.find([('name', '=', "Hour")])

    >>> template = ProductTemplate()
    >>> template.name = "Machine"
    >>> template.type = 'assets'
    >>> template.default_uom = unit
    >>> template.account_category = account_category
    >>> template.rentable = True
    >>> template.rental_per_day = True
    >>> template.rental_unit = day
    >>> rental_price = template.rental_prices.new()
    >>> rental_price.duration = dt.timedelta(days=7)
    >>> rental_price.price = Decimal('840.0000')
    >>> rental_price = template.rental_prices.new()
    >>> rental_price.duration = dt.timedelta(days=1)
    >>> rental_price.price = Decimal('180.0000')
    >>> template.save()
    >>> machine, = template.products

Create a rentable service::

    >>> template = ProductTemplate()
    >>> template.name = "Service"
    >>> template.type = 'service'
    >>> template.default_uom = unit
    >>> template.account_category = account_category
    >>> template.rentable = True
    >>> template.rental_unit = hour
    >>> rental_price = template.rental_prices.new()
    >>> rental_price.duration = dt.timedelta(hours=1)
    >>> rental_price.price = Decimal('20.0000')
    >>> template.save()
    >>> service, = template.products

Create customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Rent 5 assets and 1 service::

    >>> rental = Rental()
    >>> rental.party = customer
    >>> line = rental.lines.new()
    >>> line.product = machine
    >>> line.per_day
    True
    >>> line.quantity = 5
    >>> line.planned_start_day = today
    >>> line.planned_end_day = today + dt.timedelta(days=10)
    >>> line.unit_price
    Decimal('120.0000')
    >>> assertEqual(line.unit_price_unit, day)
    >>> line.planned_amount
    Decimal('6000.00')
    >>> line.amount
    Decimal('6000.00')
    >>> rental.untaxed_amount
    Decimal('6000.00')
    >>> rental.tax_amount
    Decimal('600.00')
    >>> rental.total_amount
    Decimal('6600.00')

    >>> line = rental.lines.new()
    >>> line.product = service
    >>> line.quantity = 1
    >>> line.planned_start = now
    >>> line.planned_end = now + dt.timedelta(hours=5)
    >>> line.unit_price
    Decimal('20.0000')
    >>> assertEqual(line.unit_price_unit, hour)

    >>> rental.save()
    >>> rental.untaxed_amount
    Decimal('6100.00')
    >>> rental.tax_amount
    Decimal('610.00')
    >>> rental.total_amount
    Decimal('6710.00')

Quote the rental::

    >>> rental.click('quote')
    >>> rental.state
    'quotation'
    >>> line_machine, line_service = rental.lines
    >>> outgoing_move, = line_machine.outgoing_moves
    >>> outgoing_move.state
    'draft'
    >>> outgoing_move.quantity
    5.0
    >>> assertEqual(outgoing_move.planned_date, line_machine.start)
    >>> incoming_move, = line_machine.incoming_moves
    >>> outgoing_move.state
    'draft'
    >>> outgoing_move.quantity
    5.0
    >>> line_service.outgoing_moves
    []
    >>> line_service.incoming_moves
    []

Go back to draft::

    >>> rental.click('draft')
    >>> rental.state
    'draft'

Confirm the rental::

    >>> rental.click('quote')
    >>> rental.click('confirm')
    >>> rental.state
    'confirmed'

Pickup some::

    >>> pickup = rental.click('pickup')
    >>> assertEqual(pickup.form.start, rental.start)
    >>> line_machine, line_service = pickup.form.lines
    >>> line_machine.quantity_picked = 2
    >>> line_service.quantity_picked = 1
    >>> pickup.execute('pickup')

    >>> len(rental.lines)
    3

    >>> late_line, = [l for l in rental.lines if l.rental_state == 'confirmed']
    >>> late_line.quantity
    3.0

Pickup remaining later::

    >>> pickup = rental.click('pickup')
    >>> pickup.form.start = now + dt.timedelta(days=1)
    >>> line, = pickup.form.lines
    >>> line.quantity_picked = 3
    >>> pickup.execute('pickup')

    >>> rental.state
    'picked up'

Partially return earlier::

    >>> return_ = rental.click('return_')
    >>> return_.form.end = rental.end - dt.timedelta(days=1)
    >>> line = return_.form.lines[0]
    >>> line.quantity_returned = 1
    >>> return_.execute('return_')

    >>> len(rental.lines)
    4

Partially invoice::

    >>> rental.has_lines_to_invoice
    True
    >>> rental.click('invoice')
    >>> rental.has_lines_to_invoice
    False

    >>> invoice, = Invoice.find([])
    >>> len(invoice.lines)
    1
    >>> invoice.total_amount
    Decimal('1188.00')

Return remaining::

    >>> return_ = rental.click('return_')
    >>> assertEqual(return_.form.end, rental.end)
    >>> len(return_.form.lines)
    3
    >>> for line in return_.form.lines:
    ...     line.quantity_returned = line.quantity
    >>> return_.execute('return_')

    >>> rental.state
    'done'
    >>> rental.has_lines_to_invoice
    False

    >>> invoices = Invoice.find([])
    >>> len(invoices)
    2
    >>> sum(i.total_amount for i in invoices)
    Decimal('11879.64')
