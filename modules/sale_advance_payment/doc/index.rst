Sale Advance Payment Module
###########################

The sale_advance_payment module adds support for advance payment management on
the sale.

The module adds a new document: the Advance Payment Term that defines how the
shipment or the supply processes should be managed. Either process can be
completely delayed until the advance payments are paid.

Two new fields are added to *Sale*:

- *Advance Payment Term*
- *Advance Payment Conditions*

The conditions are computed at the quotation of the sale if a payment term is
set.

When the sale is processed the advance payment invoices are created, final
invoices will be generated when this advance payment invoices are paid. Those
invoices will take into the account the amount previously paid by the customer.

.. warning::
    If an advance payment invoice is cancelled and not recreated when
    processing the exception. The condition of the cancelled invoice will be
    concidered as met.
..

Advance Payment Term
********************

It defines how advance payment invoices should be created and what they block
until they are paid.

- Name: The name of the term.
- Lines:

  - Description: The description used for the invoice line.
  - Account: The account used for the invoice line. If it has default taxes,
    the taxes will be applied.
  - Block Supply: If checked, it prevents the creation of any supply request
    before the payment of the advance payment invoice.
  - Block Shipping: If checked, the shipments can not be packed before the
    payment of the advance payment invoice.
  - Invoice Delay: The delay to apply on the sale date for the date of the
    advance payment invoice.
  - Formula: It computes the amount of the invoice line.
