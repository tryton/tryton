Analytic Account Module
#######################

The analytic account module adds the fundamentals required to analyse
accounting using multiple different axes.

A chart of analytic accounts can be setup for each axis.

Account
*******

An analytic account is defined by these fields:

- Name
- Code
- Company
- Type:

    - Root: define an axis
    - View: sum amounts of children accounts
    - Normal: store analytic lines
    - Distribution: distribute linked lines between different accounts

- Parent
- Balance/Credit/Debit
- State:

    - Draft
    - Opened
    - Closed

- Note

Line
****

An analytic line defines the amount of money from a move line to be assigned to
an analytic account. It contains the following fields:

- Debit/Credit
- Account
- Move Line
- Date

When the linked move is posted, an analytic state is calculated for each of the
move lines. It is only valid if all the analytic axes have been completely
filled.
The incomplete lines can be found in the menu entry "Analytic Lines to
Complete".

Rule
****

The module contains a rule engine that can automatically create analytic lines
when the move is posted, but only if they do not already have analytic lines.
The criteria for the rule engine are:

- Account
- Party
- Journal
