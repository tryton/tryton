======================
Invoice Tax Deductible
======================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts, create_tax)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_invoice')

    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')

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

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create party::

    >>> party = Party(name="Party")
    >>> party.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.supplier_taxes_deductible_rate = Decimal('.5')
    >>> account_category.supplier_taxes.append(tax)
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('100')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Post a supplier invoice with 0% deductible::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> line.unit_price = Decimal('50')
    >>> line.taxes_deductible_rate
    Decimal('0.5')
    >>> line.taxes_deductible_rate = Decimal(0)
    >>> line.amount
    Decimal('550.00')
    >>> invoice.untaxed_amount, invoice.tax_amount, invoice.total_amount
    (Decimal('550.00'), Decimal('0.00'), Decimal('550.00'))
    >>> invoice.click('post')
    >>> invoice.untaxed_amount, invoice.tax_amount, invoice.total_amount
    (Decimal('550.00'), Decimal('0'), Decimal('550.00'))
    >>> len(invoice.taxes)
    0

Post a supplier invoice with 50% deductible rate::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> line.unit_price = Decimal('50')
    >>> line.amount
    Decimal('525.00')
    >>> invoice.untaxed_amount, invoice.tax_amount, invoice.total_amount
    (Decimal('525.00'), Decimal('25.00'), Decimal('550.00'))
    >>> invoice.click('post')
    >>> invoice.untaxed_amount, invoice.tax_amount, invoice.total_amount
    (Decimal('525.00'), Decimal('25.00'), Decimal('550.00'))
    >>> len(invoice.taxes)
    1
