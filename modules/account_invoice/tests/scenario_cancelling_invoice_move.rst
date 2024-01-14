================================
Cancelling Invoice Move Scenario
================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.exceptions import CancelInvoiceMoveWarning
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('account_invoice')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Invoice = Model.get('account.invoice')
    >>> Warning = Model.get('res.user.warning')

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

Create party::

    >>> party = Party(name="Party")
    >>> party.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')

Post invoice and cancel the created move::

    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> cancel_move = Wizard('account.move.cancel', [invoice.move])
    >>> cancel_move.form.description = 'Cancel'
    >>> cancel_move.execute('cancel')
    Traceback (most recent call last):
        ...
    CancelInvoiceMoveWarning: ...

Bypass the warning and cancel the move::

    >>> try:
    ...     cancel_move.execute('cancel')
    ... except CancelInvoiceMoveWarning as e:
    ...     Warning(user=config.user, name=e.name).save()
    >>> cancel_move.execute('cancel')
    >>> cancel_move.state
    'end'

    >>> invoice.reload()
    >>> [bool(l.reconciliation) for l in invoice.move.lines
    ...     if l.account == accounts['receivable']]
    [True]
    >>> invoice.state
    'paid'
