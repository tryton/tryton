Account Statement Module
########################

The account_statement module allows to book statements. Statement can be used
for bank statement, cash daybook etc.

Statement
*********

A statement groups many lines under a journal for a date. It is mainly defined
by:

- Name.
- Journal.
- Date.

The statement can be in one of this states:

* Draft

  The statement is waiting for validation

* Validated

  The statement is validated and is waiting to be posted. The moves for each
  line are already created in draft state.

* Posted

  The statement is posted which means all the moves have been posted.

* Canceled

  The statement is canceled which means all the moves previously created have
  been deleted.

Line
****

A Statement Line is mainly defined by:

- Date.
- Amount.
- Party.
- Account.
- Invoice.
- Description.

Journal
*******

A Statement Journal is mainly defined by:

- Name.
- Journal (from account).
- Currency.
- Validation Type:
  - Balance
  - Amount
  - Number of Lines

The statements are validated following the validation type of the journal.
The Balance validation requests to set the start and end balance (the start is
automaticaly filled with the end balance of the last statement on the same
journal) and the difference is checked against the total amount of the lines.
The Amount validation requests to set the total amount to check against the
total amount of the lines.
The Number of Lines requests to set the number of unique lines on the
statement.
