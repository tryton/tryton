Commission Module
#################

The commission module allows to manage commission for sale's agent.
A commission move is created when posting the invoice, following the agent's
commission plan.

Agent
*****

An agent links a party with a commission plan and method.

- The *Plan* is the commission plan.
- The *Account* is the payable account on which the commission will be
  credited.
- The *Commission Method* defines when the commission will be due:
    - *On Posting*: when the invoice is posted.
    - *On Payment*: when the invoice is paid.

Commission Plan
***************

A plan contains a sets of lines that defines the formula to use to compute the
commission amount. The line is selected by choosing the first that matches the
criteria.

- The *Commission Product* is used to debit the commission using its expense
  account.

Line
----

- The *Formula* is a Python expression that will be evaluated with `amount` as
  the invoiced amount.

The criteria:

- *Product*.
