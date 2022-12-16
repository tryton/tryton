Account Cash Rounding Module
############################

The account_cash_rounding module allows cash amounts to be rounded using the
cash rounding factor of the currency.

When the invoice has to round the lines to pay, the exceeded amount is debited
or credited to the accounts defined on the accounting configuration.

Sales and invoices have the rounding activated by default based on the
accounting configuration flag. Purchase use the last purchase for the supplier
as the default value and transfer the value to the created invoices.
