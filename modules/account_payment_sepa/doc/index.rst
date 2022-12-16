Account Payment SEPA Module
###########################

The account_payment_sepa module allows to generate SEPA files for a Payment
Group.


Journal
*******

The Journal has some fields when the process method is SEPA:

- Bank Account Number.
- Payable Flavor:
  - pain.001.001.03
  - pain.001.001.05
  - pain.001.003.05
- Receivable Flavor:
  - pain.008.001.02
  - pain.008.001.04
  - pain.008.003.02
- Payable/Receivable Initiator Identifier:
  - SEPA Creditor Identifier
  - Belgian Enterprise Number
  - Spanish VAT Number
- Batch Booking.
- Charge Bearer:
  - Debtor
  - Creditor
  - Shared
  - Service Level

Group
*****

The Group has a field `SEPA Messages` containing the XML messages.

Mandate
*******

The Mandate stores information for the Direct Debit. It is mainly defined by:

- Party.
- Account Number.
- Identification.
- Type:
  - Recurrent
  - One-off
- Scheme:
  - CORE
  - Business to Business
- Signature Date

The mandate can be in one of this states:

* Draft
* Requested
* Validated
* Cancelled

Message
*******

The Message stores the incoming and outgoing XML message.

The message can be in one of this states:

* Draft
* Waiting
* Done
* Cancelled

Bank to Customer Debit Credit Notification (camt.054)
-----------------------------------------------------

For incoming message camt.054, each booked entry will succeed the corresponding
payment if any return information is found. Otherwise it will fail and the
return reason will be stored on it.

Party
*****

The Party has a field `SEPA Creditor Identifier` used for the party of the
company.


Configuration
*************

The account_payment_sepa module uses the section `account_payment_sepa` to
retrieve some parameters:

- `filestore`: a boolean value to store SEPA message in the FileStore.
  The default value is `False`.

- `store_prefix`: the prefix to use with the FileStore. The default value is
  `None`.
