Account Module
##############

The account module define fundamentals for most of accounting needs.


Fiscal Year
***********

A fiscal year aggregate a set of periods that are included between two
dates. A Fiscal year can be *Open* or *Closed*. Closing a fiscal year
will close all the corresponding periods.

- Name: The name of the fiscal year.
- Code: The code.
- Starting and Ending Date: The dates in which the periods should be
  included.
- Company: The company for which the fiscal year is defined.
- State: Can be *Open* or *Closed*.
- Periods: The list of periods.
- Post Move Sequence: The sequence to use for numbering moves in this
  fiscal year.


Period
******

A period is mainly defined by a Starting and an Ending date, a Fiscal
Year, a Type and a State (*Open* or *Closed* ).

The type can be *Standard* or *Adjustement*: Periods of type
*Standard* on the same fiscal year can not overlap. Period of type
*Adjustement* can overlap other periods and are typically used for all
the accounting moves that must be created when closing a fiscal year.

Each account move must be linked to a period and a move must be
created on an open period.


Account Type
************

The Account Type Model define the structure of the accounting reports:

- Income Statement: A checkbox that tells if accounts of this type
  must appear at the top level of the Income Statement report.
- Balance Sheet: A checkbox that tells if accounts of this type
  must appear at the top level of the Balance Sheet report.
- Display Balance: A selection that allow to choose how the balance
  should be computed (Debit - Credit or Credit - Debit)


Account
*******

An Account is defined by these fields:

- Name
- Code
- Company
- Parent Account
- Currency
- kind: can take one of these values:

  - Payable or Receivable: if the account is used respectively on
    credit and debit moves of parties.
  - Expense or Revenue: if the account is used respectively on expense
    and revenue moves of parties.
  - View: means that the account is used to group other accounts in
    the account chart.
  - Other: For other accounts.

- Type: The Account Type of the account.
- Deferral: A checkbox. If set to true, credits and debits are carried
  over form fiscal year to fiscal year.
- Second currency: Force all moves for the account to have this
  secondary currency.
- Reconcile: Allow move lines of this account to be reconciled.
- A list of tax: This auto-complete move with new moves lines
  corresponding to thoses taxes if the user create a line linked to
  the current account.
- Note


Journal
*******

A Journal contains the following fields:

- Name
- Code
- Active: A checkbox that allow to disable the tax.
- View: Defines how the moves lines of this journal should be
  displayed.
- Centralised counterpart: If true all created lines are linked to the
  last open movement for the current journal and the current period.
- Update Posted: if true it allow to upated posted moves of this
  journal.
- Default Credit Account, Default Debit Account: Used as default
  accounts on move lines for centralised journals and for journal of
  *Cash* type.
- Type: By default take one of the following values: *General*,
  *Revenue*, *Expense*, *Cash*, *Situation*.


Move
****

A Move groups a list of Move Lines. It contains the following fields:

- Name
- Reference
- Period
- Journal
- Effective Date: The date the move was created.
- Post Date: The date the move was posted.
- State: Can be *Draft* or *Posted*. A move should be balanced before
  being posted. Once posted the move gets a Reference number, the
  lines are posted and they can not be edited anymore.
- Lines: The move lines.


Moves Line:
***********

A Move Line is an amount of money that is credited to or debited from
an account. The fields are:

- Name
- Reference
- Debit and Credit: Define the debited or credited amount. These two
  values can not be non-zero at the same time.
- Account: The account.
- Move: The move that links all the corresponding lines.
- State: Can take one of the following value: 

  - *Draft*: The line is part of a non-balanced move.
  - *Valid*: The line is part of a balanced move.
  - *Posted*: The line is part of a posted move.

- Second Currency and Amount Second Currency: allow to keep track of
  the original amount if the underlying transaction was made in an
  other currency.
- Maturity Date: used for payable and receivable lines. The Maturity
  Date is the limit date for the payment.
- Reconciliation: Hold a reconciliation number if applicable.
- Journal, Period, Date: The values on these fields comes from the
  corresponding move.
- Tax Lines

The *Reconcile Lines* wizard allow to link move lines of the same
acount for whose the credit sum is equal to the debit sum. If the
selected lines are not balanced, the wizard offer to create a
write-off.

The *Unreconcile Lines* wizard allow to do the inverse operation.


Tax Code
********

The tax codes defines a tree structure and are used to create the tax
reports. They are used to collect the tax amounts and the base amounts
of the invoices. The Tax Code model contains the followong fields:

- Name
- Code
- Active: A checkbox that allow to disable the tax code.
- Company: The company for which the tax code is defined.
- Parent, Children: Parent and children tax codes.
- Sum: The sum of all amounts corresponding to this tax code.


Tax
***

The tax model defines taxes, how the tax amount are computed and which
tax code to use when creating invoices. The Tax model is defined by
the following fields:

- Name
- Description
- Group
- Active: A checkbox that allow to disable the tax code.
- Sequence
- Type: May be *Percentage* or *Fixed*.
- Amount: If Type is *Fixed*, defines a fix amount for the tax.
- Percentage: If Type is *Percentage*, defines the percentage of the
  tax.
- Parent, Children: Parent and children taxes
- Company: The company for which the tax code is defined.
- Invoice Account: The account to use when creating move lines for
  invoicing with this tax.
- Credit Note Account: The account to use when creating move lines for
  credit notes with this tax.
- Invoice Base Code: The code to use for the base amount when this tax
  is used on invoices.
- Invoice Base Sign: The sign of the base amount when summed for the
  above tax code.
- Invoice Tax Code: The code to use for the tax amount when this tax
  is used on invoices.
- Invoice Tax Sign: The sign of the tax amount when summed for the
  above tax code.
- Credit Note Base Code: The code to use for the base amount when this tax
  is used on credit notes.
- Credit Note Base Sign: The sign of the base amount summed for the
  above tax code.
- Credit Note Tax Code: The code to use for the tax amount when this tax
  is used on credit notes.
- Credit Note Tax Sign: The sign of the tax amount when summed for the
  above tax code.


Templates
*********

The Template models (Account Template, Account Type Template, Tax
Template, Tax Code Template, etc) are the equivalent of their
counterparts except that they are not linked to a company. A wizard
allow to create and update from templates the corresponding objects.

