Bank Module
###########

The bank module defines the concept of bank and account.

Bank
****

A bank links a party with a `BIC`_.

.. _`BIC`: http://en.wikipedia.org/wiki/Bank_Identifier_Code

Bank Account
************

A bank account is defined by a *Bank* and at least one number.

- The *Bank* is the bank where the account is set.
- The *Owners* are the parties who own the account.
- The *Currency* is the default currency of the account.
- The *Numbers* are the different possible number that identifies the account.
  There are two types defined by default:

  - `IBAN`_
  - Other

.. _`IBAN`: http://en.wikipedia.org/wiki/IBAN
