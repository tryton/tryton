=============================================
Sale Supply with Shipment on Invoice Scenario
=============================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term

Activate modules::

    >>> config = activate_modules('sale_supply')

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

    >>> Journal = Model.get('account.journal')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> cash_journal, = Journal.find([('type', '=', 'cash')])
    >>> cash_journal.save()
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = cash_journal
    >>> payment_method.credit_account = accounts['cash']
    >>> payment_method.debit_account = accounts['cash']
    >>> payment_method.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.purchasable = True
    >>> template.list_price = Decimal('10')
    >>> template.supply_on_sale = 'always'
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Sale 5 products with shipment method on invoice::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.shipment_method = 'invoice'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'
    >>> len(sale.shipments)
    0
    >>> invoice, = sale.invoices
    >>> sale_line, = sale.lines
    >>> sale_line.purchase_request

Pay for 4 products::

    >>> invoice_line, = invoice.lines
    >>> invoice_line.quantity = 4
    >>> invoice.click('post')
    >>> pay = invoice.click('pay')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')

Not yet a purchase request::

    >>> sale_line.reload()
    >>> sale_line.purchase_request

Pay for remaining products::

    >>> sale.reload()
    >>> _, invoice = sale.invoices
    >>> invoice.click('post')
    >>> pay = invoice.click('pay')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')

Check purchase request::

    >>> sale_line.reload()
    >>> bool(sale_line.purchase_request)
    True
    >>> sale_line.purchase_request.quantity
    5.0
