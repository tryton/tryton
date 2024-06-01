*****
Usage
*****

.. _Setting a customer to send invoice to Chorus Pro:

Setting a customer to send invoice to Chorus Pro
================================================

To send automatically `Customer Invoices
<account_invoice:model-account.invoice>` through `Chorus Pro`_ , you must check
the :guilabel:`Chorus Pro` checkbox on the customer `Party
<party:model-party.party>` form.

.. _Resent failing invoice:

Resent failing invoice
======================

When an `Invoice <model-account.invoice.chorus>` is not accepted by `Chorus
Pro`_, it is set to the "Exception" state.
After fixing the data, you can resend the invoice by clicking on
:guilabel:`Send` button.

.. _Chorus Pro: https://portail.chorus-pro.gouv.fr/
