=====================
Sale History Scenario
=====================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Activate modules::

    >>> config = activate_modules('sale_history')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create a sale::

   >>> Sale = Model.get('sale.sale')
   >>> sale = Sale()
   >>> sale.party = customer
   >>> sale.click('quote')

   >>> sale.number
   '1'
   >>> sale.revision
   0
   >>> sale.rec_name
   '1'

Reset to draft increases revision::

   >>> sale.click('draft')

   >>> sale.revision
   1
   >>> sale.rec_name
   '1/1'
