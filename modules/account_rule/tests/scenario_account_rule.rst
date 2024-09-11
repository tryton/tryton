=====================
Account Rule Scenario
=====================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_tax, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['account_rule', 'product', 'sale'],
    ...     create_company, create_chart)

    >>> AccountRule = Model.get('account.account.rule')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')
    >>> Tax = Model.get('account.tax')

Get accounts::

    >>> accounts = get_accounts()
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
    >>> line = sale.lines.new()
    >>> line.type = 'comment'
    >>> line.description = 'Sample'
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

    >>> invoice, = sale.invoices
    >>> assertEqual(invoice.lines[0].account, account_revenue1)
    >>> assertEqual(invoice.lines[1].account, account_revenue2)
    >>> assertEqual(invoice.lines[2].account, account_revenue3)
