Account Tax Cash Module
#######################

The account_tax_cash module allows to make tax report on cash basis.

The tax groups reported on cash basis are defined on the *Fiscal Year* and
*Period*. They can also be defined on the supplier invoices which get the
default values from the *Party*.

When a payment lines is added to an invoice, the tax lines for the proportional
amount are set on the corresponding tax code for the current period.
If a payment line is removed from an invoice, the reverse operation is applied.

When closing a *Period*, a warning is raised if there are still
receivable/payable lines not reconciled or linked to an invoice.

.. warning::
    The invoice template may need to be adapated to include a legal notice when
    tax on cash basis is used. It can be tested with the *on_cash_basis*
    property of the *Invoice Tax*.
..
