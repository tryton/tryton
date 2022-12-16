=========================
Account Tax Code Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, create_tax_code

Activate modules::

    >>> config = activate_modules('account')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create tax code::

    >>> TaxCode = Model.get('account.tax.code')
    >>> tax = create_tax(Decimal('0.1'))
    >>> tax.save()
    >>> base_code = create_tax_code(tax, amount='base')
    >>> base_code.save()
    >>> tax_code_invoice = create_tax_code(tax)
    >>> tax_code_invoice.save()
    >>> tax_code_credit = create_tax_code(tax, type='credit')
    >>> tax_code_credit.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create some moves::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> journal, = Journal.find([
    ...         ('code', '=', 'EXP'),
    ...         ])

    >>> move = Move(period=period, journal=journal)
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['expense']
    >>> line.credit = Decimal(10)
    >>> line = move.lines.new()
    >>> line.account = accounts['payable']
    >>> line.debit = Decimal(11)
    >>> line.party = party
    >>> line = move.lines.new()
    >>> line.account = accounts['tax']
    >>> line.credit = Decimal(1)
    >>> tax_line = line.tax_lines.new()
    >>> tax_line.amount = line.credit
    >>> tax_line.type = 'tax'
    >>> tax_line.tax = tax
    >>> move.save()

    >>> _ = move.duplicate()

    >>> cancel_move = Wizard('account.move.cancel', [move])
    >>> cancel_move.execute('cancel')

Check tax code::

    >>> TaxCode = Model.get('account.tax.code')

    >>> with config.set_context(periods=[period.id]):
    ...     tax_code_invoice = TaxCode(tax_code_invoice.id)
    ...     tax_code_credit = TaxCode(tax_code_credit.id)
    >>> tax_code_invoice.amount, tax_code_credit.amount
    (Decimal('1.00'), Decimal('0.00'))
