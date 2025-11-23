=====================================
Sale Rental Progress Invoice Scenario
=====================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today() - dt.timedelta(days=30)
    >>> now = dt.datetime.combine(today, dt.time(8))

Activate modules::

    >>> config = activate_modules(
    ...     'sale_rental_progress_invoice', create_company, create_chart)

    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Rental = Model.get('sale.rental')

Get accounts::

    >>> accounts = get_accounts()

Create account category::

    >>> account_category = ProductCategory(name="Account")
    >>> account_category.accounting = True
    >>> account_category.account_rental = accounts['revenue']
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
    >>> rental_price.duration = dt.timedelta(days=1)
    >>> rental_price.price = Decimal('50.0000')
    >>> template.save()
    >>> asset, = template.products

Create customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Rent the asset::

    >>> rental = Rental(party=customer)
    >>> line = rental.lines.new()
    >>> line.product = asset
    >>> line.quantity = 4
    >>> line.planned_start_day = today
    >>> line.planned_end_day = today + dt.timedelta(days=30)
    >>> rental.click('quote')
    >>> rental.click('confirm')

    >>> rental.state
    'confirmed'
    >>> rental.total_amount
    Decimal('6000.00')

Pickup::

    >>> pickup = rental.click('pickup')
    >>> pickup.form.start = now
    >>> line, = pickup.form.lines
    >>> line.quantity_picked = 2
    >>> pickup.execute('pickup')

Add progress::

    >>> add_progress = rental.click('add_progress')
    >>> add_progress.form.date = today + dt.timedelta(days=10)
    >>> add_progress.execute('add')

Invoice progress::

    >>> rental.has_lines_to_invoice
    True
    >>> rental.click('invoice')
    >>> rental.has_lines_to_invoice
    False

    >>> invoice, = Invoice.find([])
    >>> invoice_line, = invoice.lines
    >>> assertEqual(invoice_line.origin.duration, dt.timedelta(days=10))
    >>> invoice.total_amount
    Decimal('1000.00')

Partially return::

    >>> return_ = rental.click('return_')
    >>> return_.form.end = now + dt.timedelta(days=15)
    >>> line, = return_.form.lines
    >>> line.quantity_returned = 1
    >>> return_.execute('return_')

    >>> len(rental.lines)
    3

Add progress::

    >>> add_progress = rental.click('add_progress')
    >>> add_progress.form.date = today + dt.timedelta(days=20)
    >>> add_progress.execute('add')

Invoice progress::

    >>> rental.click('invoice')

    >>> invoice, = Invoice.find([('id', '!=', invoice.id)])
    >>> len(invoice.lines)
    2
    >>> assertEqual(
    ...     {l.origin.duration for l in invoice.lines},
    ...     {dt.timedelta(days=15), dt.timedelta(days=10)})
    >>> invoice.total_amount
    Decimal('750.00')

Remove pending line::

    >>> rental.click('draft')
    >>> draft_line, = [l for l in rental.lines if l.rental_state == 'draft']
    >>> rental.lines.remove(draft_line)
    >>> rental.click('quote')
    >>> rental.click('confirm')
    >>> rental.state
    'picked up'

Return remaining::

    >>> return_ = rental.click('return_')
    >>> line, = return_.form.lines
    >>> line.quantity_returned = 1
    >>> return_.execute('return_')

    >>> invoices = Invoice.find([])
    >>> len(invoices)
    3
    >>> sum(i.total_amount for i in invoices)
    Decimal('2250.00')
