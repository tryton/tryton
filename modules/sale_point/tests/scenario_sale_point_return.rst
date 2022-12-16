===================
POS Scenario Return
===================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

Activate modules::

    >>> config = activate_modules('sale_point')

Get models::

    >>> Journal = Model.get('account.journal')
    >>> Location = Model.get('stock.location')
    >>> POS = Model.get('sale.point')
    >>> PaymentMethod = Model.get('sale.point.payment.method')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.point.sale')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')

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

Create tax::

    >>> tax = create_tax(Decimal('.21'))
    >>> tax.save()

Create account categories::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.customer_taxes.append(tax)
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.account_category = account_category
    >>> template.gross_price = Decimal('12.0000')
    >>> template.list_price
    Decimal('9.9174')
    >>> template.save()
    >>> goods, = template.products

Get journal::

    >>> journal_revenue, = Journal.find([('type', '=', 'revenue')], limit=1)

Get stock locations::

    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> input_loc, = Location.find([('code', '=', 'IN')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Create POS::

    >>> pos = POS(name="POS")
    >>> pos.journal = journal_revenue
    >>> pos.sequence = SequenceStrict(name="POS", company=pos.company)
    >>> pos.sequence.sequence_type, = SequenceType.find(
    ...     [('name', '=', "POS")], limit=1)
    >>> pos.sequence.save()
    >>> pos.storage_location = storage_loc
    >>> pos.return_location = input_loc
    >>> pos.customer_location = customer_loc
    >>> pos.save()

Create payment method::

    >>> cash_method = PaymentMethod(name="Cash")
    >>> cash_method.account = accounts['cash']
    >>> cash_method.cash = True
    >>> cash_method.save()

Make a sale::

    >>> sale = Sale(point=pos)

    >>> line = sale.lines.new()
    >>> line.product = goods
    >>> line.quantity = -1

    >>> sale.save()
    >>> sale.total
    Decimal('-12.00')

Add payment::

    >>> payment = sale.payments.new()
    >>> payment.method = cash_method
    >>> payment.amount
    Decimal('-12.00')
    >>> sale.save()
    >>> sale.amount_to_pay
    Decimal('0.00')

    >>> sale.click('process')
    >>> sale.state
    'done'

Post the sale::

    >>> sale.click('post')
    >>> sale.state
    'posted'

Check stock move::

    >>> line, = sale.lines
    >>> move, = line.moves
    >>> move.product == goods
    True
    >>> move.from_location == customer_loc
    True
    >>> move.to_location == input_loc
    True
    >>> move.state
    'done'

Check account move::

    >>> bool(sale.move)
    True

    >>> accounts['revenue'].reload()
    >>> accounts['revenue'].debit, accounts['revenue'].credit
    (Decimal('9.92'), Decimal('0.00'))

    >>> accounts['tax'].reload()
    >>> accounts['tax'].debit, accounts['tax'].credit
    (Decimal('2.08'), Decimal('0.00'))

    >>> accounts['cash'].reload()
    >>> accounts['cash'].debit, accounts['cash'].credit
    (Decimal('0.00'), Decimal('12.00'))
