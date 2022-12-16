=========================
Account Tax Cash Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, create_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

Activate modules::

    >>> config = activate_modules('account_tax_cash')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Set Cash journal::

    >>> Journal = Model.get('account.journal')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> journal_cash, = Journal.find([('type', '=', 'cash')])
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = journal_cash
    >>> payment_method.credit_account = account_cash
    >>> payment_method.debit_account = account_cash
    >>> payment_method.save()

Create taxes::

    >>> Tax = Model.get('account.tax')
    >>> TaxGroup = Model.get('account.tax.group')
    >>> TaxCode = Model.get('account.tax.code')

    >>> group_cash_basis = TaxGroup(name="Cash Basis", code="CASH")
    >>> group_cash_basis.save()
    >>> tax_cash_basis = create_tax(Decimal('.10'))
    >>> tax_cash_basis.group = group_cash_basis
    >>> tax_cash_basis.save()
    >>> code_base_cash_basis = create_tax_code(tax_cash_basis, 'base', 'invoice')
    >>> code_base_cash_basis.save()
    >>> code_tax_cash_basis = create_tax_code(tax_cash_basis, 'tax', 'invoice')
    >>> code_tax_cash_basis.save()

    >>> fiscalyear.tax_group_on_cash_basis.append(TaxGroup(group_cash_basis.id))
    >>> fiscalyear.save()

    >>> group_no_cash_basis = TaxGroup(name="No Cash Basis", code="NOCASH")
    >>> group_no_cash_basis.save()
    >>> tax_no_cash_basis = create_tax(Decimal('.05'))
    >>> tax_no_cash_basis.group = group_no_cash_basis
    >>> tax_no_cash_basis.save()
    >>> code_base_no_cash_basis = create_tax_code(tax_no_cash_basis, 'base', 'invoice')
    >>> code_base_no_cash_basis.save()
    >>> code_tax_no_cash_basis = create_tax_code(tax_no_cash_basis, 'tax', 'invoice')
    >>> code_tax_no_cash_basis.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.invoice_date = period.start_date
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100')
    >>> line.account = revenue
    >>> line.taxes.extend([Tax(tax_cash_basis.id), Tax(tax_no_cash_basis.id)])
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('115.00')
    >>> invoice.move.state
    'posted'

Check tax lines::

    >>> TaxLine = Model.get('account.tax.line')

    >>> lines = TaxLine.find([])
    >>> len(lines)
    4
    >>> any(l.on_cash_basis for l in lines if l.tax == tax_no_cash_basis)
    False
    >>> all(l.on_cash_basis for l in lines if l.tax == tax_cash_basis)
    True

Check tax codes::

    >>> with config.set_context(periods=[period.id]):
    ...     TaxCode(code_base_cash_basis.id).amount
    ...     TaxCode(code_tax_cash_basis.id).amount
    Decimal('0.00')
    Decimal('0.00')

    >>> with config.set_context(periods=[period.id]):
    ...     TaxCode(code_base_no_cash_basis.id).amount
    ...     TaxCode(code_tax_no_cash_basis.id).amount
    Decimal('100.00')
    Decimal('5.00')

Pay partially the invoice::

    >>> pay = Wizard('account.invoice.pay', [invoice],
    ...     context={'payment_date': period.start_date})
    >>> pay.form.amount = Decimal('60')
    >>> pay.form.payment_method = payment_method
    >>> pay.form.date = period.start_date
    >>> pay.execute('choice')
    >>> pay.form.type = 'partial'
    >>> pay.execute('pay')

Check tax codes::

    >>> with config.set_context(periods=[period.id]):
    ...     TaxCode(code_base_cash_basis.id).amount
    ...     TaxCode(code_tax_cash_basis.id).amount
    Decimal('52.17')
    Decimal('5.22')

    >>> with config.set_context(periods=[period.id]):
    ...     TaxCode(code_base_no_cash_basis.id).amount
    ...     TaxCode(code_tax_no_cash_basis.id).amount
    Decimal('100.00')
    Decimal('5.00')
