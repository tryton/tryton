=======================================
Account Tax Cash Reconsilition Scenario
=======================================

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

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> payment_term = PaymentTerm(name="2x")
    >>> line = payment_term.lines.new(type='percent', ratio=Decimal('0.5'))
    >>> line = payment_term.lines.new(type='remainder')
    >>> payment_term.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.invoice_date = period.start_date
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100')
    >>> line.account = revenue
    >>> line.taxes.extend([Tax(tax_cash_basis.id)])
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('110.00')
    >>> invoice.move.state
    'posted'

Check tax lines::

    >>> TaxLine = Model.get('account.tax.line')

    >>> lines = TaxLine.find([])
    >>> len(lines)
    2
    >>> all(l.on_cash_basis for l in lines if l.tax == tax_cash_basis)
    True

Check tax codes::

    >>> with config.set_context(periods=[period.id]):
    ...     TaxCode(code_base_cash_basis.id).amount
    ...     TaxCode(code_tax_cash_basis.id).amount
    Decimal('0.00')
    Decimal('0.00')

Pay 1 term of the invoice::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')

    >>> journal_cash, = Journal.find([('type', '=', 'cash')])
    >>> move = Move()
    >>> move.date = period.start_date
    >>> move.journal = journal_cash
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.debit = Decimal('55')
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.party = party
    >>> line.credit = Decimal('55')
    >>> move.save()

    >>> payment_line, = [l for l in move.lines if l.account == receivable]
    >>> term1 = [l for l in invoice.move.lines if l.account == receivable][0]

    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [payment_line, term1],
    ...     context={'payment_date': period.start_date})
    >>> reconcile_lines.state == 'end'
    True

Check tax codes::

    >>> with config.set_context(periods=[period.id]):
    ...     TaxCode(code_base_cash_basis.id).amount
    ...     TaxCode(code_tax_cash_basis.id).amount
    Decimal('50.00')
    Decimal('5.00')
