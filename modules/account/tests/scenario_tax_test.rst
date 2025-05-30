=========================
Account Tax Test Scenario
=========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_tax, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('account', create_company, create_chart)

Get accounts::

    >>> accounts = get_accounts()

Create tax::

    >>> tax = create_tax(Decimal('0.1'))
    >>> tax.save()

Test Tax::

    >>> tax_test = Wizard('account.tax.test')
    >>> tax_test.form.unit_price = Decimal('100.00')
    >>> tax_test.form.taxes.append(tax)
    >>> result, = tax_test.form.result
    >>> assertEqual(result.tax, tax)
    >>> assertEqual(result.account, accounts['tax'])
    >>> assertEqual(result.base, Decimal('100.00'))
    >>> assertEqual(result.amount, Decimal('10.00'))
