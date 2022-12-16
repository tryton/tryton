==================================
Account Invoice Watermark Scenario
==================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Report, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

    >>> from trytond.modules.account_invoice_watermark.tests.tools import (
    ...     pdf_contains)

Activate modules::

    >>> config = activate_modules('account_invoice_watermark')

    >>> ActionReport = Model.get('ir.action.report')
    >>> Invoice = Model.get('account.invoice')
    >>> Journal = Model.get('account.journal')
    >>> Party = Model.get('party.party')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')

Convert invoice report to PDF::

    >>> invoice_report, = ActionReport.find([
    ...     ('report_name', '=', 'account.invoice'),
    ...     ])
    >>> invoice_report.extension = 'pdf'
    >>> invoice_report.save()

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

Create payment method::

    >>> journal_cash, = Journal.find([('type', '=', 'cash')])
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = journal_cash
    >>> payment_method.credit_account = accounts['cash']
    >>> payment_method.debit_account = accounts['cash']
    >>> payment_method.save()

Create party::

    >>> party = Party(name='Party')
    >>> party.save()

Create invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = 10
    >>> line.unit_price = Decimal('4.2000')
    >>> invoice.save()

Print draft invoice::

    >>> invoice_report = Report('account.invoice')
    >>> content = invoice_report.execute([invoice])[1]
    >>> pdf_contains(content, "DRAFT")
    True

Print posted invoice::

    >>> invoice.click('post')
    >>> content = invoice_report.execute([invoice])[1]
    >>> pdf_contains(content, "DRAFT")
    False
    >>> pdf_contains(content, "PAID")
    False

Print paid invoice::

    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> invoice.state
    'paid'
    >>> content = invoice_report.execute([invoice])[1]
    >>> pdf_contains(content, "PAID")
    True
