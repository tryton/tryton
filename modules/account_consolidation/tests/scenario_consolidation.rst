==============================
Account Consolidation Scenario
==============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Report

    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company

Activate modules::

    >>> config = activate_modules(['account_consolidation'])

    >>> Company = Model.get('company.company')
    >>> Consolidation = Model.get('account.consolidation')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> User = Model.get('res.user')

Get journals::

    >>> expense_journal, = Journal.find([('code', '=', 'EXP')])
    >>> revenue_journal, = Journal.find([('code', '=', 'REV')])

Create currencies::

    >>> usd = get_currency('USD')
    >>> eur = get_currency('EUR')

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create companies::

    >>> party = Party(name="Dunder Mifflin")
    >>> party.save()
    >>> _ = create_company(party, usd)
    >>> dunder_mifflin, = Company.find([('party', '=', party.id)], limit=1)

    >>> party = Party(name="Saber")
    >>> party.save()
    >>> _ = create_company(party, eur)
    >>> saber, = Company.find([('party', '=', party.id)], limit=1)

    >>> user = User(config.user)
    >>> user.company_filter = 'all'
    >>> user.companies.extend([dunder_mifflin, saber])
    >>> user.save()
    >>> set_user(user.id)


Create fiscal year for Dunder Mifflin::

    >>> fiscalyear = create_fiscalyear(dunder_mifflin)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts for Dunder Mifflin::

    >>> _ = create_chart(dunder_mifflin)
    >>> accounts_dunder = get_accounts(dunder_mifflin)

Create some moves for Dunder Mifflin::

    >>> move = Move(company=dunder_mifflin)
    >>> move.journal = revenue_journal
    >>> move.period = period
    >>> line = move.lines.new(
    ...     account=accounts_dunder['receivable'],
    ...     party=customer,
    ...     debit=Decimal('200.00'))
    >>> line = move.lines.new(
    ...     account=accounts_dunder['revenue'],
    ...     credit=Decimal('200.00'))
    >>> move.click('post')

    >>> move = Move(company=dunder_mifflin, consolidation_company=saber)
    >>> move.journal = expense_journal
    >>> move.period = period
    >>> line = move.lines.new(
    ...     account=accounts_dunder['payable'],
    ...     party=saber.party,
    ...     credit=Decimal('100.00'))
    >>> line = move.lines.new(
    ...     account=accounts_dunder['expense'],
    ...     debit=Decimal('100.00'))
    >>> move.click('post')

Create fiscal year for Saber::

    >>> fiscalyear = create_fiscalyear(saber)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts for Saber::

    >>> _ = create_chart(saber)
    >>> accounts_saber = get_accounts(saber)

Create same moves for Saber::

    >>> move = Move(company=saber, consolidation_company=dunder_mifflin)
    >>> move.journal = revenue_journal
    >>> move.period = period
    >>> line = move.lines.new(
    ...     account=accounts_saber['receivable'],
    ...     party=dunder_mifflin.party,
    ...     debit=Decimal('50.00'))
    >>> line = move.lines.new(
    ...     account=accounts_saber['revenue'],
    ...     credit=Decimal('50.00'))
    >>> move.click('post')

    >>> move = Move(company=saber)
    >>> move.journal = expense_journal
    >>> move.period = period
    >>> line = move.lines.new(
    ...     account=accounts_saber['payable'],
    ...     party=supplier,
    ...     credit=Decimal('40.00'))
    >>> line = move.lines.new(
    ...     account=accounts_saber['expense'],
    ...     debit=Decimal('40.00'))
    >>> move.click('post')

 Setup consolidation::

    >>> balance_group = Consolidation(name="Balance")
    >>> balance_group.statement = 'balance'
    >>> receivable_group = balance_group.children.new(
    ...     name="Receivable", assets=True)
    >>> receivable_group.types.append(accounts_dunder['receivable'].type)
    >>> receivable_group.types.append(accounts_saber['receivable'].type)
    >>> payable_group = balance_group.children.new(
    ...     name="Payable")
    >>> payable_group.types.append(accounts_dunder['payable'].type)
    >>> payable_group.types.append(accounts_saber['payable'].type)
    >>> balance_group.save()

    >>> income_group = Consolidation(name="Income")
    >>> income_group.statement = 'income'
    >>> income_group.save()

    >>> revenue_group = Consolidation(name="Revenue")
    >>> revenue_group.statement = 'income'
    >>> revenue_group.parent = income_group
    >>> revenue_group.types.append(accounts_dunder['revenue'].type)
    >>> revenue_group.types.append(accounts_saber['revenue'].type)
    >>> revenue_group.save()

    >>> expense_group = Consolidation(name="Expense")
    >>> expense_group.statement = 'income'
    >>> expense_group.parent = income_group
    >>> expense_group.types.append(accounts_dunder['expense'].type)
    >>> expense_group.types.append(accounts_saber['expense'].type)
    >>> expense_group.save()

Check consolidation amount only for Dunder Mifflin::

    >>> with config.set_context(
    ...         companies=[dunder_mifflin.id], currency=usd.id):
    ...     Consolidation(balance_group.id).amount
    Decimal('-100.00')

    >>> with config.set_context(
    ...         companies=[dunder_mifflin.id], currency=eur.id):
    ...     Consolidation(balance_group.id).amount
    Decimal('-200.00')

    >>> with config.set_context(
    ...         companies=[dunder_mifflin.id], currency=usd.id):
    ...     Consolidation(income_group.id).amount
    Decimal('100.00')

Check consolidation amount only for Dunder Mifflin and Saber::

    >>> with config.set_context(
    ...         companies=[dunder_mifflin.id, saber.id], currency=usd.id):
    ...     Consolidation(balance_group.id).amount
    Decimal('-180.00')

    >>> with config.set_context(
    ...         companies=[dunder_mifflin.id, saber.id], currency=usd.id):
    ...     Consolidation(income_group.id).amount
    Decimal('180.00')

Test report::

    >>> statement = Report('account.consolidation.statement')
    >>> with config.set_context(
    ...         companies=[dunder_mifflin.id, saber.id], currency=usd.id):
    ...     _ = statement.execute(Consolidation.find([]))
