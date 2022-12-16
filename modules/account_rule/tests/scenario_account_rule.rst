=====================
Account Rule Scenario
=====================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts, create_tax)

Activate modules::

    >>> config = activate_modules(['account_rule', 'product', 'sale'])

    >>> AccountRule = Model.get('account.account.rule')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')
    >>> Tax = Model.get('account.tax')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> account_revenue1 = accounts['revenue']
    >>> account_revenue2, = account_revenue1.duplicate()
    >>> account_revenue3, = account_revenue1.duplicate()

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Setup account rule::

    >>> rule1 = AccountRule(type='revenue')
    >>> rule1.tax = tax
    >>> rule1.account = account_revenue2
    >>> rule1.save()

    >>> rule2 = AccountRule(type='revenue')
    >>> rule2.origin_account = account_revenue1
    >>> rule2.return_ = True
    >>> rule2.account = account_revenue3
    >>> rule2.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = account_revenue1
    >>> account_category.save()

Create product::

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom, = ProductUom.find([('name', '=', "Unit")])
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.account_category = account_category
    >>> template.salable = True
    >>> template.save()
    >>> product, = template.products

Create customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Test rules with a sale::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.taxes.append(Tax(tax.id))
    >>> line.quantity = 2
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = -1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

    >>> invoice, = sale.invoices
    >>> invoice.lines[0].account == account_revenue1
    True
    >>> invoice.lines[1].account == account_revenue2
    True
    >>> invoice.lines[2].account == account_revenue3
    True
