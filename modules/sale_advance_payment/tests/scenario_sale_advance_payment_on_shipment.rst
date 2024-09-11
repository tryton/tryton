=========================================
Sale Advance Payment On Shipment Scenario
=========================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.sale_advance_payment.tests.tools import (
    ...     add_advance_payment_accounts, create_advance_payment_term)
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale_advance_payment', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Party = Model.get('party.party')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUoM = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

Get accounts::

    >>> accounts = add_advance_payment_accounts(get_accounts())

Create a fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Set a payment method::

    >>> cash_journal, = Journal.find([('type', '=', 'cash')])
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = "Cash"
    >>> payment_method.journal = cash_journal
    >>> payment_method.credit_account = accounts['cash']
    >>> payment_method.debit_account = accounts['cash']
    >>> payment_method.save()

Create a product::

    >>> unit, = ProductUoM.find([('name', '=', "Unit")])

    >>> account_category = ProductCategory(name="Accounting")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

    >>> template = ProductTemplate(name="Product")
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20.0000')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create a customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create an advance payment term::

    >>> advance_payment_term = create_advance_payment_term(
    ...     "Advance Payment", '0.1 * total_amount', accounts['advance_payment'],
    ...     block_supply=True, delay=0)
    >>> advance_payment_term.save()

Sell products::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.advance_payment_term = advance_payment_term
    >>> sale.invoice_method = 'shipment'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> sale.click('quote')
    >>> sale.total_amount
    Decimal('200.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'
    >>> len(sale.shipments)
    0
    >>> len(sale.invoices)
    0

Pay the advance payment invoice::

    >>> invoice, = sale.advance_payment_invoices
    >>> invoice.total_amount
    Decimal('20.00')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

    >>> pay = invoice.click('pay')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> invoice.state
    'paid'

    >>> sale.reload()
    >>> len(sale.shipments)
    1
    >>> len(sale.invoices)
    0

Make a partial shipment::

    >>> shipment, = sale.shipments
    >>> move, = shipment.inventory_moves
    >>> move.quantity = 5
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')

    >>> sale.reload()
    >>> len(sale.shipments)
    2
    >>> len(sale.invoices)
    1

    >>> invoice, = sale.invoices
    >>> invoice.total_amount
    Decimal('80.00')

Ship backorder::

    >>> _, shipment = sale.shipments
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')

    >>> sale.reload()
    >>> len(sale.shipments)
    2
    >>> len(sale.invoices)
    2

    >>> _, invoice = sale.invoices
    >>> invoice.total_amount
    Decimal('100.00')
