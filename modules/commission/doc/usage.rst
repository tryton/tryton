*****
Usage
*****

.. _Setting automatically the agent when selling to a customer:

Setting automatically the agent when selling to a customer
==========================================================

Sometimes you want to have the same `Agent <model-commission.agent>` always set
when selling to a specific *Customer*.
You can define the *Agent* on the `Party <party:model-party.party>` form for
a period (or leave the dates empty for any period).

.. _Rewarding employee salesman with commission:

Rewarding employee salesman with commission
===========================================

You must create an `Agent <model-commission.agent>` for each `Employee
<company:model-company.employee>`.
Then for each *Agent* opens the *Selections* related records and create an
`Agent Selection <model-commission.agent.selection>` only filled with the
corresponding *Employee*.
