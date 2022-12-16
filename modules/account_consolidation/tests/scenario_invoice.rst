================
Invoice Scenario
================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model

    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company

Activate modules::

    >>> config = activate_modules(['account_consolidation', 'account_invoice'])

    >>> Company = Model.get('company.company')
    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')

Create companies::

    >>> party = Party(name="Dunder Mifflin")
    >>> party.save()
    >>> _ = create_company(party)
    >>> dunder_mifflin, = Company.find([('party', '=', party.id)], limit=1)

    >>> party = Party(name="Saber")
    >>> party.save()
    >>> _ = create_company(party)
    >>> saber, = Company.find([('party', '=', party.id)], limit=1)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(dunder_mifflin))
    >>> fiscalyear.click('create_period')
    >>> period_ids = [p.id for p in fiscalyear.periods]

Create chart of accounts::

    >>> _ = create_chart(dunder_mifflin)
    >>> accounts = get_accounts(dunder_mifflin)

Create invoice::

    >>> invoice = Invoice()
    >>> invoice.party = saber.party
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('10.0000')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Check consolidation company::

    >>> invoice.consolidation_company == saber
    True
    >>> invoice.move.consolidation_company == saber
    True
