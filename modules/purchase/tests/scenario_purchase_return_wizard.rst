===============================
Purchase Return Wizard Scenario
===============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('purchase', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create account categories::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'service'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.purchasable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_category = account_category
    >>> template.save()
    >>> service, = template.products

Return purchase using the wizard::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase_to_return = Purchase()
    >>> purchase_to_return.party = supplier
    >>> purchase_line = purchase_to_return.lines.new()
    >>> purchase_line.product = service
    >>> purchase_line.quantity = 1
    >>> purchase_line.unit_price = Decimal('10.0000')
    >>> purchase_line = purchase_to_return.lines.new()
    >>> purchase_line.type = 'comment'
    >>> purchase_line.description = 'Test comment'
    >>> purchase_to_return.click('quote')
    >>> purchase_to_return.click('confirm')
    >>> purchase_to_return.state
    'processing'
    >>> return_purchase = Wizard('purchase.return_purchase', [
    ...     purchase_to_return])
    >>> return_purchase.execute('return_')
    >>> returned_purchase, = Purchase.find([
    ...     ('state', '=', 'draft'),
    ...     ])
    >>> assertEqual(returned_purchase.origin, purchase_to_return)
    >>> sorted([x.quantity or 0 for x in returned_purchase.lines])
    [-1.0, 0]
