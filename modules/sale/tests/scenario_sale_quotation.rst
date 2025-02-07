=======================
Sale Quotation Scenario
=======================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('sale', create_company, create_chart)

    >>> Cron = Model.get('ir.cron')
    >>> Sale = Model.get('sale.sale')
    >>> SaleConfiguration = Model.get('sale.configuration')
    >>> Party = Model.get('party.party')

Set quotation validity to 1 week::

    >>> sale_configuration = SaleConfiguration(1)
    >>> sale_configuration.sale_quotation_validity = dt.timedelta(weeks=1)
    >>> sale_configuration.save()

Create customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create a quotation::

    >>> sale = Sale(party=customer)
    >>> sale.click('quote')
    >>> sale.state
    'quotation'
    >>> assertEqual(sale.quotation_date, today)
    >>> assertEqual(sale.quotation_validity, dt.timedelta(weeks=1))
    >>> assertEqual(sale.quotation_expire, today + dt.timedelta(weeks=1))

Expire quotation::

    >>> sale.quotation_date = today - dt.timedelta(weeks=2)
    >>> sale.save()

    >>> cron, = Cron.find(
    ...     [('method', '=', 'sale.sale|cancel_expired_quotation')], limit=1)
    >>> cron.click('run_once')

    >>> sale.reload()
    >>> sale.state
    'cancelled'
