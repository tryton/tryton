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
- Receivable Flavor:
  - pain.008.001.02
  - pain.008.001.04
- Batch Booking.
- Charge Bearer:
  - Debtor
  - Creditor
  - Shared
  - Service Level

Group
*****

The Group has a field `SEPA Message` containing the XML file.

Mandate
*******

The Mandate stores information for the Direct Debit. It is mainly defined by:

- Party.
- Account Number.
- Identification.
- Type:
  - Recurrent
  - One-off
- Signature Date

The mandate can be in one of this states:

* Draft
* Requested
* Validated
* Canceled

Party
*****

The Party has a field `SEPA Creditor Identifier` used for the party of the
company.
