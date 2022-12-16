======================
Move Template Scenario
======================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code

Install account::

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
    >>> payable = accounts['payable']
    >>> expense = accounts['expense']
    >>> tax = accounts['tax']

Create tax with code::

    >>> tax = set_tax_code(create_tax(Decimal('0.1')))
    >>> tax.save()

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
    >>> line = template.lines.new()
    >>> line.operation = 'debit'
    >>> line.account = expense
    >>> line.amount = 'amount / 1.1'
    >>> ttax = line.taxes.new()
    >>> ttax.amount = line.amount
    >>> ttax.code = tax.invoice_base_code
    >>> ttax.tax = tax
    >>> line = template.lines.new()
    >>> line.operation = 'debit'
    >>> line.account = tax.invoice_account
    >>> line.amount = 'amount * (1 - 1/1.1)'
    >>> ttax = line.taxes.new()
    >>> ttax.amount = line.amount
    >>> ttax.code = tax.invoice_tax_code
    >>> ttax.tax = tax
    >>> template.save()

Create Move::

    >>> create_move = Wizard('account.move.template.create')
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
    >>> move.description
    u'Supplier - Test'
    >>> tax.invoice_base_code.sum
    Decimal('11.13')
    >>> tax.invoice_tax_code.sum
    Decimal('1.11')
