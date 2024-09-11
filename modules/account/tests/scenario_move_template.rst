======================
Move Template Scenario
======================

Imports::

    >>> import datetime
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, create_tax, create_tax_code, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import (
    ...     activate_modules, assertEqual, assertGreaterEqual, assertLessEqual)

    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('account', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period_ids = [p.id for p in fiscalyear.periods]

Get accounts::

    >>> accounts = get_accounts()
    >>> payable = accounts['payable']
    >>> expense = accounts['expense']
    >>> tax = accounts['tax']

Create tax code::

    >>> TaxCode = Model.get('account.tax.code')
    >>> tax = create_tax(Decimal('0.1'))
    >>> tax.save()
    >>> base_code = create_tax_code(tax, amount='base')
    >>> base_code.save()
    >>> tax_code = create_tax_code(tax)
    >>> tax_code.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create Template::

    >>> MoveTemplate = Model.get('account.move.template')
    >>> Journal = Model.get('account.journal')
    >>> template = MoveTemplate()
    >>> template.name = 'Test'
    >>> template.journal, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])
    >>> _ = template.keywords.new(name='party', string='Party',
    ...     type_='party')
    >>> _ = template.keywords.new(name='description', string='Description',
    ...     type_='char')
    >>> _ = template.keywords.new(name='amount', string='Amount',
    ...     type_='numeric', digits=2)
    >>> template.description = '{party} - {description}'
    >>> line = template.lines.new()
    >>> line.operation = 'credit'
    >>> line.account = payable
    >>> line.party = 'party'
    >>> line.amount = 'amount'
    >>> line.description = "{description} 1"
    >>> line = template.lines.new()
    >>> line.operation = 'debit'
    >>> line.account = expense
    >>> line.amount = 'amount / 1.1'
    >>> ttax = line.taxes.new()
    >>> ttax.amount = line.amount
    >>> ttax.tax = tax
    >>> ttax.type = 'base'
    >>> line.description = "{description} 2"
    >>> line = template.lines.new()
    >>> line.operation = 'debit'
    >>> line.account = tax.invoice_account
    >>> line.amount = 'amount * (1 - 1/1.1)'
    >>> line.description = "{description} 3"
    >>> ttax = line.taxes.new()
    >>> ttax.amount = line.amount
    >>> ttax.tax = tax
    >>> ttax.type = 'tax'
    >>> template.save()

Create Move::

    >>> create_move = Wizard('account.move.template.create')
    >>> assertEqual(create_move.form.date, today)
    >>> period = create_move.form.period
    >>> assertLessEqual(period.start_date, today)
    >>> assertGreaterEqual(period.end_date, today)
    >>> index = fiscalyear.periods.index(create_move.form.period)
    >>> next_period = fiscalyear.periods[index + 1]
    >>> create_move.form.date = next_period.start_date
    >>> assertEqual(create_move.form.period, next_period)
    >>> prev_period = fiscalyear.periods[index - 1]
    >>> create_move.form.period = prev_period
    >>> assertEqual(create_move.form.date, prev_period.end_date)
    >>> create_move.form.period = next_period
    >>> assertEqual(create_move.form.date, next_period.start_date)
    >>> create_move.form.template = template
    >>> create_move.execute('keywords')
    >>> data = {}
    >>> keywords = data['keywords'] = {}
    >>> keywords['party'] = supplier.id
    >>> keywords['description'] = 'Test'
    >>> keywords['amount'] = Decimal('12.24')
    >>> context = create_move._context.copy()
    >>> context.update(create_move._config.context)
    >>> _ = create_move._proxy.execute(create_move.session_id, data, 'create_',
    ...     context)

.. note:: using custom call because proteus doesn't support fake model

Check the Move::

    >>> Move = Model.get('account.move')
    >>> move, = Move.find([])
    >>> len(move.lines)
    3
    >>> sorted((l.debit, l.credit) for l in move.lines)
    [(Decimal('0'), Decimal('12.24')), (Decimal('1.11'), Decimal('0')), (Decimal('11.13'), Decimal('0'))]
    >>> sorted([l.description for l in move.lines])
    ['Test 1', 'Test 2', 'Test 3']
    >>> move.description
    'Supplier - Test'
    >>> with config.set_context(periods=period_ids):
    ...     base_code = TaxCode(base_code.id)
    ...     base_code.amount
    Decimal('11.13')
    >>> with config.set_context(periods=period_ids):
    ...     tax_code = TaxCode(tax_code.id)
    ...     tax_code.amount
    Decimal('1.11')
