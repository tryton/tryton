========================================
Account ES SSI Renew Fiscalyear Scenario
========================================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

Activate modules::

    >>> config = activate_modules('account_es_sii')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear = set_fiscalyear_invoice_sequences(fiscalyear)
    >>> fiscalyear.click('create_period')

    >>> last_period = fiscalyear.periods[-1]
    >>> last_period.es_sii_send_invoices = True
    >>> last_period.save()

    >>> period = fiscalyear.periods.new()
    >>> period.name = 'Adjustment'
    >>> period.start_date = fiscalyear.end_date
    >>> period.end_date = fiscalyear.end_date
    >>> period.type = 'adjustment'
    >>> fiscalyear.save()

    >>> fiscalyear.es_sii_send_invoices

Renew fiscal year having last period sending invoices::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = False
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> bool(new_fiscalyear.es_sii_send_invoices)
    True

Renew fiscal year having last period not sending invoices::

    >>> last_period = new_fiscalyear.periods[-1]
    >>> last_period.es_sii_send_invoices = False
    >>> last_period.save()

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = False
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> bool(new_fiscalyear.es_sii_send_invoices)
    False
