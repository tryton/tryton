===================================
Invoice Scenario Alternate Currency
===================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, create_tax, get_accounts)
    >>> from trytond.modules.account_invoice.exceptions import InvoiceTaxesWarning
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> tomorrow = today + dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('account_invoice', create_company, create_chart)

    >>> Warning = Model.get('res.user.warning')

Get currencies::

    >>> currency = get_currency('USD')
    >>> eur = get_currency('EUR')

Set alternate currency rates::

    >>> rate = eur.rates.new()
    >>> rate.date = today
    >>> rate.rate = eur.rates[0].rate
    >>> rate = eur.rates.new()
    >>> rate.date = tomorrow
    >>> rate.rate = eur.rates[0].rate + Decimal('0.5')
    >>> eur.save()

Create fiscal years::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=(today, tomorrow)))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create payment method::

    >>> Journal = Model.get('account.journal')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> Sequence = Model.get('ir.sequence')
    >>> journal_cash, = Journal.find([('type', '=', 'cash')])
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = journal_cash
    >>> payment_method.credit_account = account_cash
    >>> payment_method.debit_account = account_cash
    >>> payment_method.save()

Create writeoff method::

    >>> WriteOff = Model.get('account.move.reconcile.write_off')
    >>> sequence_journal, = Sequence.find(
    ...     [('sequence_type.name', '=', "Account Journal")])
    >>> journal_writeoff = Journal(name='Write-Off', type='write-off',
    ...     sequence=sequence_journal)
    >>> journal_writeoff.save()
    >>> writeoff = WriteOff()
    >>> writeoff.name = 'Rate loss'
    >>> writeoff.journal = journal_writeoff
    >>> writeoff.credit_account = expense
    >>> writeoff.debit_account = expense
    >>> writeoff.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.customer_taxes.append(tax)
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create invoice with alternate currency::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.currency = eur
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('80')
    >>> line.amount
    Decimal('400.00')
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> line.amount
    Decimal('20.00')
    >>> invoice.untaxed_amount
    Decimal('420.00')
    >>> invoice.tax_amount
    Decimal('40.00')
    >>> invoice.total_amount
    Decimal('460.00')
    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.untaxed_amount
    Decimal('420.00')
    >>> invoice.tax_amount
    Decimal('40.00')
    >>> invoice.total_amount
    Decimal('460.00')

Create negative tax::

    >>> negative_tax = create_tax(Decimal('-.10'))
    >>> negative_tax.save()

Create invoice with alternate currency and negative taxes::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.currency = eur
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('80')
    >>> _ = line.taxes.pop(0)
    >>> line.taxes.append(negative_tax)
    >>> line.amount
    Decimal('400.00')
    >>> invoice.untaxed_amount
    Decimal('400.00')
    >>> invoice.tax_amount
    Decimal('-40.00')
    >>> invoice.total_amount
    Decimal('360.00')
    >>> try:
    ...     invoice.click('post')
    ... except InvoiceTaxesWarning as warning:
    ...     _, (key, *_) = warning.args
    ...     raise
    Traceback (most recent call last):
        ...
    InvoiceTaxesWarning: ...
    >>> Warning(user=config.user, name=key).save()
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.untaxed_amount
    Decimal('400.00')
    >>> invoice.tax_amount
    Decimal('-40.00')
    >>> invoice.total_amount
    Decimal('360.00')

