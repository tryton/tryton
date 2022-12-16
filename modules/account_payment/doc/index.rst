Account Payment Module
######################

The account_payment module allows to generate grouped payments for receivable
or payable Account Move Lines.

Payment
*******

A Payment defines the attempt to pay an amount to a party or to receive an
amount from a party. It is mainly defined by:

- Journal.
- Kind:
  - Payable
  - Receivable
- Party.
- Line.
- Amount.
- Date.
- Description.

A payment can be created from an payable or receivable *Account Move Line*
using the `Pay Lines` action. The amount is computed from the debit/credit
deducing existing payments for this line.

The payment can be in one of this states:

* Draft

  The payment is waiting for approval.

* Approved

  The payment has been approved and is waiting to be processed by the wizard in
  a Group.

* Processing

  The payment has been processed in a Group.

* Succeeded

  The payment was successfully processed.

* Failed

  The payment was not successfully processed.

Group
*****

A group links a set of payment of the same kind processed together inside the
same journal.

Journal
*******

A journal defines the configuration of the processing of payments.
