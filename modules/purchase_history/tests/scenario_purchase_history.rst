=========================
Purchase History Scenario
=========================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('purchase_history', create_company)

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create a purchase::

   >>> Purchase = Model.get('purchase.purchase')
   >>> purchase = Purchase()
   >>> purchase.party = supplier
   >>> purchase.click('quote')

   >>> purchase.number
   '1'
   >>> purchase.revision
   0
   >>> purchase.rec_name
   '1'

Reset to draft increases revision::

   >>> purchase.click('draft')

   >>> purchase.revision
   1
   >>> purchase.rec_name
   '1/1'
