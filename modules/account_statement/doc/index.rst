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

  The statement is validated and is waiting to be posted. A move for each
  grouped lines is already created in draft state.

* Posted

  The statement is posted which means all the moves have been posted.

* Canceled

  The statement is canceled which means all the moves previously created have
  been deleted.

Line
****

A Statement Line is mainly defined by:

- Sequence: Use to order the lines in the statement.
- Number: The number to identify a transaction.
- Date.
- Amount.
- Party.
- Account.
- Invoice.
- Description.
- Move: The move created for this line.

Origin
******

The statement origin store the raw information from an external system that
are imported. The origin are converted into statement lines.

Line Group
**********

The line group represent the group of lines created at the validation of the
statement.
By default the lines of a statement are grouped by *Number*, *Date* and *Party*.

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

Import Statement
****************

A wizard to import statements from an external system. It creates statements
with origins filled.

Configuration
*************

The account_statement module uses the section `account_statement` to retrieve
some parameters:

- `filestore`: a boolean value to store origin file in the FileStore.
  The default value is `False`.

- `store_prefix`: the prefix to use with the FileStore.
  The default value is `None`.
