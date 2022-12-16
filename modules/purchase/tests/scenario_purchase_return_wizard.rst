===============================
Purchase Return Wizard Scenario
===============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()


Activate modules::

    >>> config = activate_modules('purchase')

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
    >>> service, = template.products
    >>> service.cost_price = Decimal('10')
    >>> template.save()
    >>> service, = template.products

Return purchase using the wizard::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase_to_return = Purchase()
    >>> purchase_to_return.party = supplier
    >>> purchase_line = purchase_to_return.lines.new()
    >>> purchase_line.product = service
    >>> purchase_line.quantity = 1
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
    >>> returned_purchase.origin == purchase_to_return
    True
    >>> sorted([x.quantity or 0 for x in returned_purchase.lines])
    [-1.0, 0]
