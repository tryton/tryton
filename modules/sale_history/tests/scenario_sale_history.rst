=====================
Sale History Scenario
=====================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale_history', create_company)

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
