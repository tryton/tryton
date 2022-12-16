Account Module
##############

The account module defines fundamentals for most of accounting needs.


Fiscal Year
***********

A fiscal year aggregates a set of periods that are included between
two dates. A Fiscal year can be *Open*, *Closed* or *Locked*. Closing a fiscal
year will close all the corresponding periods. A *Locked* fiscal can not be
re-open.

- Name: The name of the fiscal year.
- Code: The code, useful for fast data entry and searching.
- Starting and Ending Date: The dates in which the periods should be
  included.
- Company: The company for which the fiscal year is defined.
- State: Can be *Open*, *Closed* or *Locked*.
- Periods: The list of periods.
- Post Move Sequence: The sequence to use for numbering moves in this
  fiscal year.

The *Balance Non-Deferral* wizard allow to create a move that will debit/credit
each non-deferral account in such way to have a balance equals to zero for the
fiscal year and debit/credit a counter part account.


Period
******

A period is mainly defined by a Starting and an Ending date, a Fiscal
Year, a Type and a State (*Open*, *Closed* or *Locked*).

The type can be *Standard* or *Adjustement*: Periods of type
*Standard* on the same fiscal year can not overlap. Period of type
*Adjustement* can overlap other periods and are typically used for all
the accounting moves that must be created when closing a fiscal year.
By default, the system uses only *Standard* period when creating
moves.

Each account move must be linked to a period and a move must be
created on an open period.


Account Type
************

The Account Type Model defines the structure of the accounting
reports:

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
- Start and End Date: The period for which the account can be used.
- Replaced By: the account to use after end date.
- Deferral: A checkbox. If set to true, credit and debit are carried
  over form fiscal year to fiscal year.
- Second currency: Force all moves for the account to have this
  secondary currency.
- Reconcile: Allow move lines of this account to be reconciled.
- Party Required: Make party required for move lines of this account.
- Taxes: This list of tax auto-complete move with new moves lines
  corresponding to thoses taxes if the user create a line linked to
  the current account and if the journal type is *Expense* or
  *Revenue*.
- Note


Journal
*******

A Journal contains the following fields:

- Name
- Code
- Active: A checkbox that allow to disable the tax.
- Type: By default take one of the following values: *General*,
  *Revenue*, *Expense*, *Cash*, *Situation*.


Reconcile Write Off
*******************

A reconcile write off is used to set the writeoff options when reconciling
unbalanced moves. It has the following fields:

- Name
- Company
- Journal: Will be used for creating the write off move
- Credit Account and Debit Account: The accounts used for the write off move
  depending on the amount sign.
- Active: A checkbox that allow to disable the writeoff.


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
- Debit and Credit: Define the debited or credited amount. Only one
  field can be filled.
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
- Tax Lines. Gives the distribution of the amount line on the account
  chart

The Move Line is displayed using the account's name eventualy surrounded by
parenthesis when it is a credit line.

The *Reconcile Lines* wizard allow to link move lines of the same
acount for whose the credit sum is equal to the debit sum. If the
selected lines are not balanced, the wizard offer to create a
write-off line with the difference to make the reconciliation.

The *Unreconcile Lines* wizard allow to do the inverse operation (but
doesn't reverse other operations that could have triggered by the
reconciliation).

The *Reconcile Accounts* wizard allow to process one by one each party and
account for reconciliation. The wizard tries to propose the best reconciliation
possible. The configuration `reconciliation_chunk` in `account` section allow
to define the length of lines that is allowed to search for proposal. The
default is 10.


Tax Code
********

The tax codes defines a tree structure and are used to create the tax
reports. They are used to collect the tax amounts and the base amounts
of the invoices. The Tax Code model contains the following fields:

- Name
- Code
- Active: A checkbox that allow to disable the tax code.
- Company: The company for which the tax code is defined.
- Parent, Children: Parent and children tax codes.
- Start and End date: The period for which the tax code is reported.
- Amount: The sum of lines for the selected periods:

    - Operator: `+` or `-`
    - Tax
    - Amount: *Tax* or *Base*
    - Type: *Invoice* or *Credit*


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
- Type: May be *Percentage*, *Fixed*, or *None* for empty tax.
- Amount: If Type is *Fixed*, defines a fix amount for the tax.
- Percentage: If Type is *Percentage*, defines the percentage of the
  tax.
- Update Unit Price: If checked then the unit price for further tax calculation
  will be increased by the amount of this tax.
- Parent, Children: Parent and children taxes
- Company: The company for which the tax is defined.
- Invoice Account: The account to use when creating move lines for
  invoicing with this tax, for credit on revenue or for debit on
  expense.
- Credit Note Account: The account to use when creating move lines for
  credit notes with this tax, for debit on revenue or for credit on
  expense

If a code field is left empty, the corresponding amounts will be
ignored by the tax reports.


Tax Rule
********

The tax rule defines a set of rules that will be applied when computing taxes.
It's composed by a name, it's kind and a list of lines. If a tax matches a tax
rule line, it will be replaced by the *Substituion Tax*. The *Original Tax*
will be included only if the *Keep Origin* check is checked.


Templates
*********

The Template models (Account Template, Account Type Template, Tax
Template, Tax Code Template, etc) are the equivalent of their
counterparts except that they are not linked to a company. Two wizard
(*Create Chart of Account from Template* and *Update Chart of Account
from Template*) allow to create and update the accounts from the
account templates (and consequently all other models associated to
templates).

Move Template
*************

A move template allows to configure predefined moves. A Move Template is
defined by the following fields:

- Name
- Company
- Keywords: The list of keywords used in the template.
- Journal
- Date: The date of the move. It must be leaved empty for today.
- Description: The description of the move. The keyword values can be
  substituted using the name surrounded by braces ('{' and '}').
- Lines: The list of template lines.
- Active

A wizard to create moved base on templates is available in the *Entries* menu.
The templates are also available as actions when opening a journal.

Move Template Keywords
**********************

The keywords define the values asked to user to create the move based on the
template. The fields are:

- Name
- String: The label used in the wizard form.
- Sequence: The sequence used to order the fields in the wizard form.
- Type:

  - *Char*
  - *Numeric*
  - *Date*
  - *Party*

- Required
- Digits: Only for numeric keyword.

Move Line Template
******************

- Operation: *Debit* or *Credit*
- Amount: An expression that can use any keywords to compute the amount.
- Account
- Party: Only for account that requires a party.
- Description
- Taxes: The list of template tax lines

Tax Line Template
*****************

- Amount: An expression that can use any keywords to compute the amount.
- Code: The tax code to use.
- Tax
