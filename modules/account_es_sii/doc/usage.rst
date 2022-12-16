*****
Usage
*****

Sending Invoices to SII
=======================

In order to let Tryton know that the invoices should be sent to SII you should
activate the ``Send invoices to SII`` flag on the `Fiscalyear
<account:model-account.fiscalyear>` form.
When this flag is activated Tryton creates a `SII Record
<model-account.invoice.sii>` for each invoice.
This record are sent automatically to the tax authority by a
*Scheduled Task*.

Tryton retries until the invoice is accepted by the tax authority.
