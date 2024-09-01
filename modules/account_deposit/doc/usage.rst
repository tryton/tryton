*****
Usage
*****

.. _Registering a customer deposit:

Registering a customer deposit
==============================

If you want to register a deposit from a `Customer <party:model-party.party>`,
you can create a `Customer Invoice <account_invoice:model-account.invoice>` and
add to it a line that has an `Account <account:model-account.account>` of `Type
Deposit <model-account.account.type>` and a price set to the amount to be
deposited.
Then you can post it and `register the payment <account_invoice:Paying an
invoice>` of the deposit.
