====================
POS Session Scenario
====================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts, create_tax)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

Activate modules::

    >>> config = activate_modules('sale_point')

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
    >>> Session = Model.get('sale.point.cash.session')
    >>> TransferType = Model.get('sale.point.cash.transfer.type')

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

Create account categories::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.salable = True
    >>> template.account_category = account_category
    >>> template.gross_price = Decimal('20.0000')
    >>> template.save()
    >>> product, = template.products

Get journal::

    >>> journal_revenue, = Journal.find([('type', '=', 'revenue')], limit=1)

Get stock locations::

    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Create POS::

    >>> pos = POS(name="POS")
    >>> pos.journal = journal_revenue
    >>> pos.sequence = SequenceStrict(name="POS", company=pos.company)
    >>> pos.sequence.sequence_type, = SequenceType.find(
    ...     [('name', '=', "POS")], limit=1)
    >>> pos.sequence.save()
    >>> pos.storage_location = storage_loc
    >>> pos.customer_location = customer_loc
    >>> pos.save()

Create cash payment method::

    >>> cash_method = PaymentMethod(name="Cash")
    >>> cash_method.account = accounts['cash']
    >>> cash_method.cash = True
    >>> cash_method.save()

Create transfer type::

    >>> transfer_type = TransferType(name="Bank")
    >>> transfer_type.journal, = Journal.find([('type', '=', 'cash')], limit=1)
    >>> accounts['bank'], = accounts['cash'].duplicate(default={'name': "Bank"})
    >>> transfer_type.account = accounts['bank']
    >>> transfer_type.save()

Create an initial cash session::

    >>> session = Session(point=pos)
    >>> transfer = session.transfers.new(point=pos)
    >>> transfer.type = transfer_type
    >>> transfer.amount = Decimal('100.00')
    >>> session.end_amount = Decimal('100.00')
    >>> session.save()
    >>> session.start_amount
    Decimal('0')
    >>> session.balance
    Decimal('100.00')
    >>> session.end_amount
    Decimal('100.00')

    >>> session.click('close')
    >>> session.state
    'closed'
    >>> session.click('post')
    >>> session.state
    'posted'

    >>> transfer, = session.transfers
    >>> transfer.state
    'posted'
    >>> bool(transfer.move)
    True
    >>> accounts['bank'].reload()
    >>> accounts['bank'].balance
    Decimal('-100.00')

Make a sale::

    >>> sale = Sale(point=pos)
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.save()
    >>> sale.total
    Decimal('20.00')

Pay by cash::

    >>> payment = Wizard('sale.point.sale.pay', [sale])
    >>> payment.form.method = cash_method
    >>> payment.form.amount
    Decimal('20.00')
    >>> payment.execute('pay')

    >>> sale.state
    'done'
    >>> payment, = sale.payments

Check the new session::

    >>> session = payment.session
    >>> session.state
    'open'
    >>> session.start_amount
    Decimal('100.00')
    >>> session.balance
    Decimal('20.00')

Try to close::

    >>> session.click('close')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    SessionValidationError: ...

    >>> session.end_amount = Decimal('120.00')
    >>> session.click('close')
    >>> session.state
    'closed'
