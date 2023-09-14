==================================
Document Incoming Invoice Scenario
==================================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('document_incoming_invoice')

    >>> Document = Model.get('document.incoming')
    >>> DocumentConfiguration = Model.get('document.incoming.configuration')
    >>> Party = Model.get('party.party')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of account::

    >>> _ = create_chart()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Set default supplier::

    >>> suppplier = Party(name="Supplier")
    >>> suppplier.save()

    >>> document_configuration = DocumentConfiguration(1)
    >>> document_configuration.default_supplier = suppplier
    >>> document_configuration.save()

Create incoming document::

    >>> document = Document()
    >>> document.name = 'invoice.pdf'
    >>> document.data = b'invoice'
    >>> document.company = company
    >>> document.type = 'supplier_invoice'
    >>> document.save()

Process document::

    >>> document.click('process')
    >>> invoice = document.result
    >>> invoice.party == suppplier
    True
