======================================
Document Incoming OCR Typless Scenario
======================================

Imports::

    >>> import os
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.tools import file_open
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts, create_tax)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules([
    ...     'document_incoming_ocr_typless',
    ...     'document_incoming_invoice'])

    >>> Document = Model.get('document.incoming')
    >>> OCRService = Model.get('document.incoming.ocr.service')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of account::

    >>> _ = create_chart()
    >>> accounts = get_accounts(company)

Create taxes::

    >>> tax_10 = create_tax(Decimal('0.1'), company)
    >>> tax_10.save()
    >>> tax_20 = create_tax(Decimal('0.2'), company)
    >>> tax_20.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Set default supplier::

    >>> suppplier = Party(name="Saber")
    >>> suppplier.save()

Create account category::

    >>> account_category = ProductCategory(name="Accounting")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.save()

Create product::

    >>> hour, = UoM.find([('name', '=', "Hour")])
    >>> template = ProductTemplate(name="Service")
    >>> template.default_uom = hour
    >>> template.type = 'service'
    >>> template.account_category = account_category
    >>> template.save()
    >>> service, = template.products

Setup Typless service::

    >>> ocr_service = OCRService(type='typless')
    >>> ocr_service.typless_api_key = os.getenv('TYPLESS_API_KEY')
    >>> ocr_service.typless_document_type = os.getenv('TYPLESS_DOCUMENT_TYPE')
    >>> ocr_service.save()

Create incoming document::

    >>> document = Document()
    >>> document.name = 'invoice.pdf'
    >>> with file_open(
    ...         'document_incoming_ocr_typless/tests/'
    ...         'supplier-invoice-sample.pdf',
    ...         mode='rb') as fp:
    ...     document.data = fp.read()
    >>> document.type = 'supplier_invoice'
    >>> document.save()

Process document::

    >>> document.click('process')
    >>> invoice = document.result
    >>> invoice.party == suppplier
    True
    >>> invoice.reference
    'INV-0007'
    >>> invoice.invoice_date
    datetime.date(2023, 6, 28)
    >>> invoice.payment_term_date
    datetime.date(2023, 7, 28)
    >>> len(invoice.lines)
    2
    >>> line_service, = [l for l in invoice.lines if l.product]
    >>> line_service.product == service
    True
    >>> line_service.quantity
    23.0
    >>> line_service.unit_price
    Decimal('2.5000')
    >>> line_goods, = [l for l in invoice.lines if not l.product]
    >>> line_goods.quantity
    40.0
    >>> line_goods.unit_price
    Decimal('5.0000')
    >>> len(invoice.taxes)
    2
    >>> sorted([t.amount for t in invoice.taxes])
    [Decimal('5.75'), Decimal('40.00')]
    >>> sorted([t.base for t in invoice.taxes])
    [Decimal('57.50'), Decimal('200.00')]
    >>> {t.tax for t in invoice.taxes} == {tax_10, tax_20}
    True
    >>> invoice.untaxed_amount
    Decimal('257.50')
    >>> invoice.tax_amount
    Decimal('45.75')
    >>> invoice.total_amount
    Decimal('303.25')

Send feedback::

    >>> document.click('ocr_send_feedback')
